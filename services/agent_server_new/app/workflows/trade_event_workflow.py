from __future__ import annotations

import time
import logging
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from services.market_state_engine.src.contracts import MarketStateMSL

from services.agent_server_new.domain.contracts import ActionIntent, Confidence, ExecutionPlan, RiskAllowance, RulePlan, SignalDecision
from services.agent_server_new.domain.execution_planner import build_execution_plan
from services.agent_server_new.domain.horizon_policy_gate import horizon_policy_gate, load_horizon_policy_config_from_env
from services.agent_server_new.domain.intent_resolver import resolve_intent
from services.agent_server_new.domain.msl_parser import _build_msl_from_dict
from services.agent_server_new.domain.risk_gate import RiskGateContext, risk_gate
from services.agent_server_new.domain.risk_gate_reasons import (
    RISK_GATE_REASON_DEFAULT_NORMAL,
    RISK_GATE_REASON_MSL_HORIZON_ALIGNMENT_CONFLICT,
    RISK_GATE_REASON_MSL_MARKET_FRAGILITY_HIGH,
    RISK_GATE_REASON_MSL_MARKET_FRAGILITY_MEDIUM,
    RISK_GATE_REASON_MSL_VOLATILITY_REGIME_HIGH,
    RISK_GATE_REASON_POSITION_COOLDOWN_ACTIVE,
    risk_gate_reason_active_event,
    risk_gate_reason_portfolio_risk_state,
)
from services.agent_server_new.domain.rule_planner import build_rule_plan
from services.agent_server_new.domain.signal_decision_agent import (
    RoutedHybridSignalDecisionAgent,
    RoutedRuleBasedSignalDecisionAgent,
    SignalDecisionAgent,
)
from services.agent_server_new.domain.signal_decision_context_policy import build_llm_observation_context
from services.agent_server_new.domain.signal_router import route_signal_agent_key
from services.agent_server_new.domain.strategy_gate import strategy_gate_v2
from services.agent_server_new.experts.signal_evaluator import evaluate_signal
from services.agent_server_new.observability.decision_trace import DecisionTrace
from services.agent_server_new.observability.decision_trace import map_alert_codes_from_contract_warnings
from services.agent_server_new.observability.decision_trace_schema_guard import validate_decision_trace_payload
from services.agent_server_new.ports.data.active_events_provider import ActiveEventsProvider
from services.agent_server_new.ports.data.position_context_provider import PositionContextProvider
from services.agent_server_new.ports.event_recorder import EventRecorder
from services.agent_server_new.ports.memory.symbol_memory_provider import SymbolMemoryProvider
from services.agent_server_new.ports.memory.symbol_memory_recorder import SymbolMemoryRecorder
from services.agent_server_new.ports.execution import ExecutionDecisionProvider
from services.agent_server_new.ports.llm_observer import LLMObserver
from services.agent_server_new.ports.market_state import MarketStateProvider
from services.agent_server_new.app.context_builder import ContextBuilder
from .event_context import EventContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TradeEventInput:
    """事件中心推送的最小输入集合（示例）。"""

    event_id: str
    exchange: str
    symbol: str
    signal_direction: str
    payload: Dict[str, Any]


@dataclass(frozen=True)
class WorkflowResult:
    """工作流输出：保留 agent 计划，并附带 execution 最终裁决（如可用）。"""

    agent_plan: ExecutionPlan
    signal_decision: SignalDecision
    execution_result: Optional[Dict[str, Any]] = None


def _extract_cross_horizon_policy(key_market_features: Dict[str, Any]) -> Dict[str, str]:
    feats = list((key_market_features or {}).get("features") or [])
    for item in feats:
        if str((item or {}).get("name") or "") != "cross_horizon":
            continue
        value = dict((item or {}).get("value") or {})
        return {
            "suggested_policy": str(value.get("suggested_policy") or "no_action"),
            "policy_reason": str(value.get("policy_reason") or "insufficient_evidence"),
        }
    return {"suggested_policy": "no_action", "policy_reason": "insufficient_evidence"}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _sha256_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _signal_router_config_version(cfg: Dict[str, Any]) -> str:
    if not isinstance(cfg, dict):
        return ""
    try:
        stable = json.dumps(cfg, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        return ""
    return _sha256_text(stable)[:16]


def _sanitize_llm_contract_error_code(value: Any) -> str:
    code = str(value or "").strip()
    allowed = {
        "",
        "llm_raw_content_missing",
        "llm_json_parse_error",
        "llm_json_not_object",
        "llm_schema_validation_failed",
        "llm_confidence_parse_error",
    }
    return code if code in allowed else "llm_schema_validation_failed"


def _sanitize_llm_contract_errors(values: Any, *, limit: int = 8) -> list[str]:
    out: list[str] = []
    for item in list(values or []):
        text = str(item or "").strip()
        if not text:
            continue
        out.append(text)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _pipeline_mode(legacy_pipeline_enabled: bool) -> str:
    return "legacy" if bool(legacy_pipeline_enabled) else "minimal"


def _derive_global_regime(
    *,
    msl: MarketStateMSL,
    position_context: Dict[str, Any],
    active_events: list[Dict[str, Any]],
) -> tuple[str, list[str]]:
    regime_rank = {"normal": 0, "elevated": 1, "critical": 2}
    regime = "normal"
    reasons: list[str] = []

    def _raise(next_regime: str, reason: str) -> None:
        nonlocal regime
        if reason and reason not in reasons:
            reasons.append(reason)
        if regime_rank.get(next_regime, 0) > regime_rank.get(regime, 0):
            regime = next_regime

    portfolio_risk = dict((position_context or {}).get("portfolio_risk") or {})
    position_risk_state = str(portfolio_risk.get("risk_state") or "normal").strip().lower()
    if position_risk_state == "frozen":
        _raise("critical", risk_gate_reason_portfolio_risk_state(position_risk_state))
    elif position_risk_state in {"reduce_only", "warn"}:
        _raise("elevated", risk_gate_reason_portfolio_risk_state(position_risk_state))

    if msl.market_fragility == "high":
        _raise("critical", RISK_GATE_REASON_MSL_MARKET_FRAGILITY_HIGH)
    elif msl.market_fragility == "medium":
        _raise("elevated", RISK_GATE_REASON_MSL_MARKET_FRAGILITY_MEDIUM)
    if str(msl.volatility.volatility_regime or "unknown") == "high":
        _raise("elevated", RISK_GATE_REASON_MSL_VOLATILITY_REGIME_HIGH)
    if msl.horizon_alignment == "conflict":
        _raise("elevated", RISK_GATE_REASON_MSL_HORIZON_ALIGNMENT_CONFLICT)

    for item in list(active_events or []):
        evt = dict(item or {})
        evt_type = str(evt.get("type") or "").strip().lower()
        score = _to_float(evt.get("score"), 0.0)
        if evt_type in {"liquidation_cluster", "forced_liquidation", "exchange_risk"} and score >= 0.8:
            _raise("critical", risk_gate_reason_active_event(evt_type, "critical"))
        elif evt_type in {"volatility_spike", "funding_extreme", "basis_dislocation"} and score >= 0.7:
            _raise("elevated", risk_gate_reason_active_event(evt_type, "elevated"))

    if not reasons:
        reasons.append(RISK_GATE_REASON_DEFAULT_NORMAL)
    return regime, reasons


def _derive_risk_gate_context(
    *,
    msl: MarketStateMSL,
    position_context: Dict[str, Any],
    active_events: list[Dict[str, Any]],
) -> tuple[RiskGateContext, list[str]]:
    pos = dict((position_context or {}).get("current_position") or {})
    cooldown_seconds_left = int(pos.get("cooldown_seconds_left") or 0)
    global_regime, reasons = _derive_global_regime(
        msl=msl,
        position_context=position_context,
        active_events=active_events,
    )
    if cooldown_seconds_left > 0 and RISK_GATE_REASON_POSITION_COOLDOWN_ACTIVE not in reasons:
        reasons.append(RISK_GATE_REASON_POSITION_COOLDOWN_ACTIVE)
    return RiskGateContext(
        global_regime=global_regime,
        cooldown_active=(cooldown_seconds_left > 0),
    ), reasons


class TradeEventWorkflow:
    """示例工作流：load context -> call expert -> rule planner -> risk gate -> execution planner -> persist。"""

    def __init__(
        self,
        *,
        market_state: MarketStateProvider,
        position_context: PositionContextProvider,
        active_events: ActiveEventsProvider,
        execution_decider: Optional[ExecutionDecisionProvider] = None,
        recorder: Optional[EventRecorder] = None,
        symbol_memory_provider: SymbolMemoryProvider | None = None,
        symbol_memory_recorder: SymbolMemoryRecorder | None = None,
        llm_observer: LLMObserver | None = None,
        decision_trace_schema_validate: bool = True,
        memory_recent_topk: int = 5,
        memory_recent_ttl_ms: int = 24 * 60 * 60 * 1000,
        memory_dedup_key: str = "event_id",
        ai_adaptive_enabled: bool = False,
        ai_adaptive_mode: str = "observe",
        legacy_pipeline_enabled: bool = True,
        horizon_policy_config: Optional[Dict[str, Any]] = None,
        signal_router_config: Optional[Dict[str, Any]] = None,
        signal_decision_agent: SignalDecisionAgent | None = None,
        signal_router_config_source: str = "runtime",
        signal_router_config_version: str = "",
    ) -> None:
        self._market_state = market_state
        self._position_context = position_context
        self._active_events = active_events
        self._execution_decider = execution_decider
        self._recorder = recorder
        self._symbol_memory_provider = symbol_memory_provider
        self._symbol_memory_recorder = symbol_memory_recorder
        self._llm_observer = llm_observer
        self._decision_trace_schema_validate = bool(decision_trace_schema_validate)
        self._memory_recent_topk = max(1, int(memory_recent_topk))
        self._memory_recent_ttl_ms = max(0, int(memory_recent_ttl_ms))
        self._memory_dedup_key = str(memory_dedup_key or "event_id").strip() or "event_id"
        self._ai_adaptive_enabled = bool(ai_adaptive_enabled)
        mode = str(ai_adaptive_mode or "observe").strip().lower()
        self._ai_adaptive_mode = mode if mode in {"observe", "recommend", "bounded_apply"} else "observe"
        self._legacy_pipeline_enabled = bool(legacy_pipeline_enabled)
        self._horizon_policy_config = dict(horizon_policy_config or load_horizon_policy_config_from_env())
        self._signal_router_config = dict(signal_router_config or {})
        self._signal_decision_agent = signal_decision_agent or (
            RoutedHybridSignalDecisionAgent(
                router_config=self._signal_router_config,
                signal_evaluator=evaluate_signal,
            )
            if self._llm_observer is not None
            else RoutedRuleBasedSignalDecisionAgent(
                router_config=self._signal_router_config,
                signal_evaluator=evaluate_signal,
            )
        )
        self._signal_router_config_source = str(signal_router_config_source or "runtime").strip() or "runtime"
        self._signal_router_config_version = str(signal_router_config_version or "").strip() or _signal_router_config_version(
            self._signal_router_config
        )

    async def run(self, event: TradeEventInput) -> ExecutionPlan:
        result = await self.run_with_result(event)
        return result.agent_plan

    async def run_with_result(self, event: TradeEventInput) -> WorkflowResult:
        builder = ContextBuilder(
            market_state=self._market_state,
            position_context=self._position_context,
            active_events=self._active_events,
            symbol_memory_provider=self._symbol_memory_provider,
            max_key_features=10,
            memory_recent_topk=self._memory_recent_topk,
            memory_recent_ttl_ms=self._memory_recent_ttl_ms,
            memory_dedup_key=self._memory_dedup_key,
        )
        built = await builder.build(
            event_id=event.event_id,
            exchange=event.exchange,
            symbol=event.symbol,
            signal_payload=event.payload,
        )
        ctx = built.ctx

        if self._recorder:
            await self._recorder.record_market_context(
                event.event_id,
                {
                    "ts": int(time.time() * 1000),
                    "symbol": ctx.symbol,
                    "msl": ctx.msl.to_llm_dict(),
                    "key_market_features": dict(ctx.key_market_features),
                    "active_events": list(ctx.active_events),
                    "position_context": dict(ctx.position_context),
                },
            )

        llm_observation = {
            "status": "disabled",
            "provider": "",
            "model": "",
            "raw_content_hash": "",
        }
        llm_result_raw: Optional[Dict[str, Any]] = None
        if self._llm_observer is not None:
            llm_agent_key = route_signal_agent_key(
                signal_event=dict(ctx.signal_event or {}),
                router_config=self._signal_router_config,
            )
            llm_ctx = build_llm_observation_context(
                decision_agent_key=llm_agent_key,
                key_market_features=dict(ctx.key_market_features or {}),
                active_events=list(ctx.active_events or []),
                features_limit=8,
                events_limit=8,
            )
            llm_payload = {
                "event_id": event.event_id,
                "exchange": event.exchange,
                "symbol": event.symbol,
                "signal_direction": event.signal_direction,
                "decision_agent_key": llm_ctx["decision_agent_key"],
                "signal_event": dict(ctx.signal_event or {}),
                "msl": ctx.msl.to_llm_dict(),
                "key_market_features": dict(llm_ctx.get("key_market_features") or {}),
                "active_events": list(llm_ctx.get("active_events") or []),
            }
            try:
                llm_result = await self._llm_observer.observe(llm_payload)
                llm_result_raw = dict(llm_result or {})
                llm_observation = {
                    "status": str((llm_result or {}).get("status") or "ok"),
                    "provider": str((llm_result or {}).get("provider") or ""),
                    "model": str((llm_result or {}).get("model") or ""),
                    "raw_content_hash": _sha256_text((llm_result or {}).get("raw_content")),
                }
                if self._recorder:
                    await self._recorder.record_agent_output(
                        event.event_id,
                        "llm_observer",
                        dict(llm_result or {}),
                    )
            except Exception as exc:
                logger.warning("llm observer failed, fallback to rule engine event_id=%s err=%s", event.event_id, exc)
                llm_observation = {
                    "status": "error",
                    "provider": "",
                    "model": "",
                    "raw_content_hash": "",
                    "fallback": "rule_engine",
                    "error_type": exc.__class__.__name__,
                }
                llm_result_raw = {"status": "error", "error_type": exc.__class__.__name__}
                if self._recorder:
                    await self._recorder.record_agent_output(
                        event.event_id,
                        "llm_observer",
                        {"status": "error", "fallback": "rule_engine", "error": str(exc)},
                    )
        eval_result = self._signal_decision_agent.decide(
            signal_direction=event.signal_direction,
            msl=ctx.msl,
            key_market_features=dict(ctx.key_market_features),
            active_events=list(ctx.active_events),
            signal_event=dict(ctx.signal_event),
            position_context=dict(ctx.position_context),
            llm_result=llm_result_raw,
        )
        signal = eval_result.signal
        signal_decision = _build_signal_decision(
            event=event,
            signal=signal,
            llm_observation=llm_observation,
            decision_agent_key=eval_result.decision_agent_key,
            decision_mode=eval_result.decision_mode,
            llm_parse_status=eval_result.llm_parse_status,
        )

        if self._recorder:
            await self._recorder.record_agent_output(
                event.event_id,
                "signal_evaluator",
                {
                    "pipeline_mode": _pipeline_mode(self._legacy_pipeline_enabled),
                    "decision_agent_key": eval_result.decision_agent_key,
                    "decision_mode": eval_result.decision_mode,
                    "llm_parse_status": eval_result.llm_parse_status,
                    "llm_contract_error_code": _sanitize_llm_contract_error_code(eval_result.llm_contract_error_code),
                    "llm_contract_errors": _sanitize_llm_contract_errors(eval_result.llm_contract_errors),
                    "direction": signal.direction,
                    "verdict": signal.verdict,
                    "confidence": {"level": signal.confidence.level, "score": signal.confidence.score},
                    "invalidation_reasons": list(signal.invalidation_reasons),
                    "notes": signal.notes,
                },
            )

        ch = _extract_cross_horizon_policy(dict(ctx.key_market_features or {}))
        position_ctx = dict(ctx.position_context or {})
        if self._legacy_pipeline_enabled:
            intent = resolve_intent(signal=signal, msl=ctx.msl, position_context=position_ctx)
            rule_plan = build_rule_plan(intent=intent, msl=ctx.msl, position_context=position_ctx)
            hpg = horizon_policy_gate(
                suggested_policy=str(ch.get("suggested_policy") or "no_action"),
                policy_reason=str(ch.get("policy_reason") or "insufficient_evidence"),
                intent=str(intent.intent),
                config=self._horizon_policy_config,
            )
            sg = strategy_gate_v2(
                msl=ctx.msl,
                signal=signal,
                intent=intent,
                rule_plan=rule_plan,
                position_context=position_ctx,
                signal_event=dict(ctx.signal_event or {}),
            )
            risk_ctx, risk_ctx_reasons = _derive_risk_gate_context(
                msl=ctx.msl,
                position_context=position_ctx,
                active_events=list(ctx.active_events),
            )
            allowance = risk_gate(risk_ctx)
            hpg_allowed = bool(hpg.allowed)
            hpg_reasons = list(hpg.reasons)
            sg_allowed = bool(sg.allowed)
            sg_reasons = list(sg.reasons)
            if not hpg_allowed:
                plan = ExecutionPlan(
                    action="skip",
                    direction="none",
                    allowance=allowance,
                    confidence=signal.confidence,
                    sizing=None,
                    notes=f"horizon_policy_gate_blocked: {','.join(hpg_reasons)}",
                )
            elif not sg_allowed:
                plan = ExecutionPlan(
                    action="skip",
                    direction="none",
                    allowance=allowance,
                    confidence=signal.confidence,
                    sizing=None,
                    notes=f"strategy_gate_blocked: {','.join(sg_reasons)}",
                )
            else:
                plan = build_execution_plan(rule_plan=rule_plan, allowance=allowance, risk_constraints={})
        else:
            intent = ActionIntent(
                intent="hold",
                direction="none",
                confidence=signal.confidence,
                reasons=["legacy_pipeline_disabled"],
                notes="legacy_pipeline_disabled",
            )
            rule_plan = RulePlan(
                intent=intent,
                sizing={},
                reasons=["legacy_pipeline_disabled"],
                notes="legacy_pipeline_disabled",
            )
            hpg_allowed = True
            hpg_reasons = ["legacy_pipeline_disabled"]
            sg_allowed = True
            sg_reasons = ["legacy_pipeline_disabled"]
            risk_ctx = RiskGateContext(global_regime="normal", cooldown_active=False)
            risk_ctx_reasons = ["legacy_pipeline_disabled"]
            allowance = RiskAllowance(
                allow_open=True,
                allow_add=True,
                allow_reduce=True,
                allow_exit=True,
                reasons=["legacy_pipeline_disabled"],
            )
            plan = ExecutionPlan(
                action="hold",
                direction="none",
                allowance=allowance,
                confidence=signal.confidence,
                sizing=None,
                notes="legacy_pipeline_disabled",
            )

        execution_result: Optional[Dict[str, Any]] = None
        if self._execution_decider is not None:
            decision_payload = _build_decision_intent_payload(
                event=event,
                signal_decision=signal_decision,
                plan=plan,
                cross_horizon=ch,
                ai_adaptive_enabled=self._ai_adaptive_enabled,
                ai_adaptive_mode=self._ai_adaptive_mode,
            )
            try:
                execution_result = await self._execution_decider.decide(decision_payload)
                logger.info(
                    "执行层裁决完成 event_id=%s action=%s reason=%s",
                    event.event_id,
                    str(execution_result.get("execution_action") or "unknown"),
                    str(execution_result.get("reject_reason") or ""),
                )
                if self._recorder:
                    await self._recorder.record_agent_output(
                        event.event_id,
                        "execution_decider",
                        execution_result,
                    )
            except Exception as exc:  # pragma: no cover
                logger.warning("执行层裁决失败 event_id=%s err=%s", event.event_id, exc)

        if self._recorder:
            await self._recorder.record_agent_output(
                event.event_id,
                "intent_resolver",
                {
                    "intent": intent.intent,
                    "direction": intent.direction,
                    "confidence": {"level": intent.confidence.level, "score": intent.confidence.score},
                    "reasons": list(intent.reasons),
                    "notes": intent.notes,
                },
            )

            await self._recorder.record_agent_output(
                event.event_id,
                "rule_planner",
                {
                    "intent": {
                        "intent": rule_plan.intent.intent,
                        "direction": rule_plan.intent.direction,
                        "confidence": {"level": rule_plan.intent.confidence.level, "score": rule_plan.intent.confidence.score},
                    },
                    "sizing": dict(rule_plan.sizing or {}),
                    "reasons": list(rule_plan.reasons),
                    "notes": rule_plan.notes,
                },
            )

            await self._recorder.record_agent_output(
                event.event_id,
                "horizon_policy_gate",
                {"allowed": hpg_allowed, "reasons": list(hpg_reasons), "cross_horizon": dict(ch)},
            )

            await self._recorder.record_agent_output(
                event.event_id,
                "strategy_gate",
                {"allowed": sg_allowed, "reasons": list(sg_reasons)},
            )

            await self._recorder.record_agent_output(
                event.event_id,
                "execution_planner",
                {
                    "action": plan.action,
                    "direction": plan.direction,
                    "sizing": dict(plan.sizing or {}),
                    "allowance": {
                        "allow_open": plan.allowance.allow_open,
                        "allow_add": plan.allowance.allow_add,
                        "allow_reduce": plan.allowance.allow_reduce,
                        "allow_exit": plan.allowance.allow_exit,
                        "reasons": list(plan.allowance.reasons),
                    },
                    "confidence": {"level": plan.confidence.level, "score": plan.confidence.score},
                    "notes": plan.notes,
                },
            )

            contract_warnings = [str(x) for x in list((ctx.key_market_features or {}).get("contract_warnings") or []) if x]
            trace = DecisionTrace(
                event_id=ctx.event_id,
                exchange=ctx.exchange,
                symbol=ctx.symbol,
                ts=ctx.timestamp_ms,
                event=dict(ctx.signal_event),
                msl=ctx.msl.to_llm_dict(),
                key_features=dict(ctx.key_market_features),
                evidence=dict((ctx.key_market_features or {}).get("evidence") or {}),
                anomalies=dict((ctx.key_market_features or {}).get("anomalies") or {}),
                signal_verdict={
                    "direction": signal.direction,
                    "verdict": signal.verdict,
                    "confidence": {"level": signal.confidence.level, "score": signal.confidence.score},
                    "invalidation_reasons": list(signal.invalidation_reasons),
                },
                routing={
                    "pipeline_mode": _pipeline_mode(self._legacy_pipeline_enabled),
                    "decision_agent_key": signal_decision.decision_agent_key,
                    "decision_mode": signal_decision.decision_mode,
                    "llm_parse_status": signal_decision.llm_parse_status,
                    "llm_contract_error_code": _sanitize_llm_contract_error_code(eval_result.llm_contract_error_code),
                    "llm_contract_errors": _sanitize_llm_contract_errors(eval_result.llm_contract_errors),
                    "router_config_source": self._signal_router_config_source,
                    "router_config_version": self._signal_router_config_version,
                },
                intent={
                    "intent": intent.intent,
                    "direction": intent.direction,
                    "confidence": {"level": intent.confidence.level, "score": intent.confidence.score},
                    "reasons": list(intent.reasons),
                },
                rule_plan={
                    "intent": {
                        "intent": rule_plan.intent.intent,
                        "direction": rule_plan.intent.direction,
                        "confidence": {"level": rule_plan.intent.confidence.level, "score": rule_plan.intent.confidence.score},
                    },
                    "sizing": dict(rule_plan.sizing or {}),
                    "reasons": list(rule_plan.reasons),
                },
                strategy_gate_result={
                    "allowed": bool(hpg_allowed and sg_allowed),
                    "horizon_reasons": list(hpg_reasons),
                    "strategy_reasons": list(sg_reasons),
                    "reasons": [*list(hpg_reasons), *list(sg_reasons)],
                },
                risk_gate={
                    "global_regime": risk_ctx.global_regime,
                    "cooldown_active": bool(risk_ctx.cooldown_active),
                    "regime_sources": list(risk_ctx_reasons),
                    "allow_open": allowance.allow_open,
                    "allow_add": allowance.allow_add,
                    "allow_reduce": allowance.allow_reduce,
                    "allow_exit": allowance.allow_exit,
                    "reasons": list(allowance.reasons),
                },
                execution_plan={
                    "action": plan.action,
                    "direction": plan.direction,
                    "sizing": dict(plan.sizing or {}),
                    "notes": plan.notes,
                },
                llm_observation=dict(llm_observation),
                memory_metrics=dict((ctx.key_market_features or {}).get("memory_observability") or {}),
                contract_warnings=contract_warnings,
                alert_codes=map_alert_codes_from_contract_warnings(contract_warnings),
                tags=["decision_trace"],
            )
            trace_payload = trace.to_dict()
            if self._decision_trace_schema_validate:
                valid, errors = validate_decision_trace_payload(trace_payload)
                if not valid:
                    logger.warning(
                        "decision_trace schema validation failed event_id=%s error_count=%s",
                        event.event_id,
                        len(errors),
                    )
                    await self._recorder.record_agent_output(
                        event.event_id,
                        "decision_trace_schema_guard",
                        {
                            "status": "invalid",
                            "error_count": len(errors),
                            "errors": list(errors[:10]),
                        },
                    )
            await self._recorder.record_agent_output(event.event_id, "decision_trace", trace_payload)

        if self._symbol_memory_recorder is not None:
            contract_warnings = [str(x) for x in list((ctx.key_market_features or {}).get("contract_warnings") or []) if x]
            await self._symbol_memory_recorder.record_symbol_memory(
                event.exchange,
                event.symbol,
                {
                    "ts": int(time.time() * 1000),
                    "event_id": event.event_id,
                    "signal_event": dict(ctx.signal_event or {}),
                    "msl_summary": str(ctx.msl.summary or ""),
                    "cross_horizon_policy": dict(ch),
                    "signal": {
                        "direction": signal.direction,
                        "verdict": signal.verdict,
                        "confidence": {"level": signal.confidence.level, "score": signal.confidence.score},
                    },
                    "intent": {
                        "intent": intent.intent,
                        "direction": intent.direction,
                        "confidence": {"level": intent.confidence.level, "score": intent.confidence.score},
                        "reasons": list(intent.reasons),
                    },
                    "plan": {
                        "action": plan.action,
                        "direction": plan.direction,
                        "notes": plan.notes,
                    },
                    "contract_warnings": contract_warnings,
                    "execution_result": dict(execution_result or {}),
                },
            )

        return WorkflowResult(agent_plan=plan, signal_decision=signal_decision, execution_result=execution_result)


def _build_decision_intent_payload(
    *,
    event: TradeEventInput,
    signal_decision: SignalDecision,
    plan: ExecutionPlan,
    cross_horizon: Dict[str, str],
    ai_adaptive_enabled: bool = False,
    ai_adaptive_mode: str = "observe",
) -> Dict[str, Any]:
    """把 agent 内部 ExecutionPlan 映射为 execution_service 的 DecisionIntent。"""

    decision_confidence = {
        "level": str(plan.confidence.level or "low"),
        "score": float(plan.confidence.score or 0.0),
    }
    payload = {
        "decision_id": str(signal_decision.decision_id or event.event_id),
        "exchange": str(signal_decision.exchange or event.exchange),
        "symbol": str(signal_decision.symbol or event.symbol),
        "direction_intent": str(signal_decision.signal_direction or "none"),
        "decision_confidence": dict(decision_confidence),
        "cross_horizon_policy": dict(cross_horizon or {}),
        "risk_hints": {
            "agent_action_hint": str(plan.action or "hold"),
            "agent_notes": str(plan.notes or ""),
            "decision_confidence": dict(decision_confidence),
            "decision_confidence_source": "agent_execution_plan",
            "decision_agent_key": str(signal_decision.decision_agent_key or ""),
            "decision_mode": str(signal_decision.decision_mode or "rule"),
            "llm_parse_status": str(signal_decision.llm_parse_status or ""),
            "signal_verdict": str(signal_decision.signal_verdict or ""),
            "signal_reliability_score": float(signal_decision.reliability_score or 0.0),
            "signal_reasons": list(signal_decision.reasons or []),
        },
    }
    if bool(ai_adaptive_enabled):
        payload["execution_hint"] = {
            "mode": "reserved",
            "adaptive_mode": str(ai_adaptive_mode or "observe"),
            "apply_scope": "none",
        }
        payload["adaptive_profile"] = {}
        payload["adaptive_profile_version"] = "reserved-v0"
        payload["adaptive_explain"] = {"status": "reserved_only"}
    return payload


def _build_signal_decision(
    *,
    event: TradeEventInput,
    signal: Any,
    llm_observation: Dict[str, Any],
    decision_agent_key: str,
    decision_mode: str,
    llm_parse_status: str,
) -> SignalDecision:
    verdict = str(getattr(signal, "verdict", "") or "uncertain").strip().lower()
    if verdict not in {"accept", "reject", "uncertain"}:
        verdict = "uncertain"
    direction = str(getattr(signal, "direction", "") or "none").strip().lower()
    if direction not in {"long", "short", "none"}:
        direction = "none"
    mode = str(decision_mode or "rule").strip().lower()
    if mode not in {"llm", "rule_fallback", "rule"}:
        mode = "rule"
    parse_status = str(llm_parse_status or "rule_only").strip().lower()
    if parse_status not in {"llm_ok", "llm_invalid_payload", "llm_status_not_ok", "llm_not_provided", "rule_only"}:
        parse_status = "rule_only"
    conf = getattr(signal, "confidence", Confidence(level="low", score=0.0))
    raw_score = float(getattr(conf, "score", 0.0) or 0.0)
    reliability_score = max(0.0, min(1.0, raw_score))
    reasons = [str(x) for x in list(getattr(signal, "invalidation_reasons", []) or []) if str(x)]
    return SignalDecision(
        decision_id=str(event.event_id),
        exchange=str(event.exchange),
        symbol=str(event.symbol),
        decision_agent_key=str(decision_agent_key or "generic"),
        decision_mode=mode,  # type: ignore[arg-type]
        llm_parse_status=parse_status,  # type: ignore[arg-type]
        signal_direction=direction,  # type: ignore[arg-type]
        signal_verdict=verdict,  # type: ignore[arg-type]
        confidence=Confidence(level=str(conf.level or "low"), score=raw_score),  # type: ignore[arg-type]
        reliability_score=reliability_score,
        reasons=reasons,
        evidence_refs=[],
        llm_observation=dict(llm_observation or {}),
    )


def _msl_from_dict(d: Dict[str, Any]) -> MarketStateMSL:
    """兼容旧测试入口，统一委托给 adapter 层单点 MSL 解析器。"""
    return _build_msl_from_dict(dict(d or {}))
