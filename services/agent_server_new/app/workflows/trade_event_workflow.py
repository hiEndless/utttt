from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from services.market_state_engine.src.contracts import MarketStateMSL

from services.agent_server_new.domain.contracts import Confidence, ExecutionPlan
from services.agent_server_new.domain.execution_planner import build_execution_plan
from services.agent_server_new.domain.horizon_policy_gate import horizon_policy_gate, load_horizon_policy_config_from_env
from services.agent_server_new.domain.intent_resolver import resolve_intent
from services.agent_server_new.domain.msl_parser import _build_msl_from_dict
from services.agent_server_new.domain.risk_gate import RiskGateContext, risk_gate
from services.agent_server_new.domain.rule_planner import build_rule_plan
from services.agent_server_new.domain.strategy_gate import strategy_gate_v2
from services.agent_server_new.experts.signal_evaluator import ExpertContext, evaluate_signal
from services.agent_server_new.observability.decision_trace import DecisionTrace
from services.agent_server_new.observability.decision_trace import map_alert_codes_from_contract_warnings
from services.agent_server_new.ports.data.active_events_provider import ActiveEventsProvider
from services.agent_server_new.ports.data.position_context_provider import PositionContextProvider
from services.agent_server_new.ports.event_recorder import EventRecorder
from services.agent_server_new.ports.memory.symbol_memory_provider import SymbolMemoryProvider
from services.agent_server_new.ports.memory.symbol_memory_recorder import SymbolMemoryRecorder
from services.agent_server_new.ports.execution import ExecutionDecisionProvider
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
        _raise("critical", "portfolio_risk_state_frozen")
    elif position_risk_state in {"reduce_only", "warn"}:
        _raise("elevated", f"portfolio_risk_state_{position_risk_state}")

    if msl.market_fragility == "high":
        _raise("critical", "msl_market_fragility_high")
    elif msl.market_fragility == "medium":
        _raise("elevated", "msl_market_fragility_medium")
    if str(msl.volatility.volatility_regime or "unknown") == "high":
        _raise("elevated", "msl_volatility_regime_high")
    if msl.horizon_alignment == "conflict":
        _raise("elevated", "msl_horizon_alignment_conflict")

    for item in list(active_events or []):
        evt = dict(item or {})
        evt_type = str(evt.get("type") or "").strip().lower()
        score = _to_float(evt.get("score"), 0.0)
        if evt_type in {"liquidation_cluster", "forced_liquidation", "exchange_risk"} and score >= 0.8:
            _raise("critical", f"active_event_{evt_type}_critical")
        elif evt_type in {"volatility_spike", "funding_extreme", "basis_dislocation"} and score >= 0.7:
            _raise("elevated", f"active_event_{evt_type}_elevated")

    if not reasons:
        reasons.append("default_normal")
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
    if cooldown_seconds_left > 0 and "position_cooldown_active" not in reasons:
        reasons.append("position_cooldown_active")
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
        memory_recent_topk: int = 5,
        memory_recent_ttl_ms: int = 24 * 60 * 60 * 1000,
        memory_dedup_key: str = "event_id",
        ai_adaptive_enabled: bool = False,
        ai_adaptive_mode: str = "observe",
        horizon_policy_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._market_state = market_state
        self._position_context = position_context
        self._active_events = active_events
        self._execution_decider = execution_decider
        self._recorder = recorder
        self._symbol_memory_provider = symbol_memory_provider
        self._symbol_memory_recorder = symbol_memory_recorder
        self._memory_recent_topk = max(1, int(memory_recent_topk))
        self._memory_recent_ttl_ms = max(0, int(memory_recent_ttl_ms))
        self._memory_dedup_key = str(memory_dedup_key or "event_id").strip() or "event_id"
        self._ai_adaptive_enabled = bool(ai_adaptive_enabled)
        mode = str(ai_adaptive_mode or "observe").strip().lower()
        self._ai_adaptive_mode = mode if mode in {"observe", "recommend", "bounded_apply"} else "observe"
        self._horizon_policy_config = dict(horizon_policy_config or load_horizon_policy_config_from_env())

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

        signal = evaluate_signal(
            ctx=ExpertContext(
                msl=ctx.msl,
                key_market_features=ctx.key_market_features,
                active_events=list(ctx.active_events),
                signal_event=ctx.signal_event,
                position_context=dict(ctx.position_context),
            ),
            signal_direction=event.signal_direction,
        )

        if self._recorder:
            await self._recorder.record_agent_output(
                event.event_id,
                "signal_evaluator",
                {
                    "direction": signal.direction,
                    "verdict": signal.verdict,
                    "confidence": {"level": signal.confidence.level, "score": signal.confidence.score},
                    "invalidation_reasons": list(signal.invalidation_reasons),
                    "notes": signal.notes,
                },
            )

        position_ctx = dict(ctx.position_context or {})
        intent = resolve_intent(signal=signal, msl=ctx.msl, position_context=position_ctx)
        rule_plan = build_rule_plan(intent=intent, msl=ctx.msl, position_context=position_ctx)
        ch = _extract_cross_horizon_policy(dict(ctx.key_market_features or {}))
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
        if not hpg.allowed:
            plan = ExecutionPlan(
                action="skip",
                direction="none",
                allowance=allowance,
                confidence=signal.confidence,
                sizing=None,
                notes=f"horizon_policy_gate_blocked: {','.join(hpg.reasons)}",
            )
        elif not sg.allowed:
            plan = ExecutionPlan(
                action="skip",
                direction="none",
                allowance=allowance,
                confidence=signal.confidence,
                sizing=None,
                notes=f"strategy_gate_blocked: {','.join(sg.reasons)}",
            )
        else:
            plan = build_execution_plan(rule_plan=rule_plan, allowance=allowance, risk_constraints={})

        execution_result: Optional[Dict[str, Any]] = None
        if self._execution_decider is not None:
            decision_payload = _build_decision_intent_payload(
                event=event,
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
                {"allowed": hpg.allowed, "reasons": list(hpg.reasons), "cross_horizon": dict(ch)},
            )

            await self._recorder.record_agent_output(
                event.event_id,
                "strategy_gate",
                {"allowed": sg.allowed, "reasons": list(sg.reasons)},
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
                    "allowed": bool(hpg.allowed and sg.allowed),
                    "horizon_reasons": list(hpg.reasons),
                    "strategy_reasons": list(sg.reasons),
                    "reasons": [*list(hpg.reasons), *list(sg.reasons)],
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
                memory_metrics=dict((ctx.key_market_features or {}).get("memory_observability") or {}),
                contract_warnings=contract_warnings,
                alert_codes=map_alert_codes_from_contract_warnings(contract_warnings),
                tags=["decision_trace"],
            )
            await self._recorder.record_agent_output(event.event_id, "decision_trace", trace.to_dict())

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

        return WorkflowResult(agent_plan=plan, execution_result=execution_result)


def _build_decision_intent_payload(
    *,
    event: TradeEventInput,
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
        "decision_id": str(event.event_id),
        "exchange": str(event.exchange),
        "symbol": str(event.symbol),
        "direction_intent": str(plan.direction or "none"),
        "decision_confidence": dict(decision_confidence),
        "cross_horizon_policy": dict(cross_horizon or {}),
        "risk_hints": {
            "agent_action_hint": str(plan.action or "hold"),
            "agent_notes": str(plan.notes or ""),
            "decision_confidence": dict(decision_confidence),
            "decision_confidence_source": "agent_execution_plan",
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


def _msl_from_dict(d: Dict[str, Any]) -> MarketStateMSL:
    """兼容旧测试入口，统一委托给 adapter 层单点 MSL 解析器。"""
    return _build_msl_from_dict(dict(d or {}))
