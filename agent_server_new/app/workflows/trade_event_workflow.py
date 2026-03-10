from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from market_state_engine.contracts import (
    KeyLevels,
    LiquidityState,
    MarketRegime,
    MarketStateMSL,
    PositioningState,
    RiskState,
    StructureState,
    VolatilityState,
)

from agent_server_new.domain.contracts import Confidence, ExecutionPlan
from agent_server_new.domain.execution_planner import build_execution_plan
from agent_server_new.domain.horizon_policy_gate import horizon_policy_gate, load_horizon_policy_config_from_env
from agent_server_new.domain.intent_resolver import resolve_intent
from agent_server_new.domain.risk_gate import RiskGateContext, risk_gate
from agent_server_new.domain.rule_planner import build_rule_plan
from agent_server_new.domain.strategy_gate import strategy_gate_v2
from agent_server_new.experts.signal_evaluator import ExpertContext, evaluate_signal
from agent_server_new.observability.decision_trace import DecisionTrace
from agent_server_new.ports.data.active_events_provider import ActiveEventsProvider
from agent_server_new.ports.data.position_context_provider import PositionContextProvider
from agent_server_new.ports.event_recorder import EventRecorder
from agent_server_new.ports.memory.symbol_memory_provider import SymbolMemoryProvider
from agent_server_new.ports.memory.symbol_memory_recorder import SymbolMemoryRecorder
from agent_server_new.ports.execution import ExecutionDecisionProvider
from agent_server_new.ports.market_state import MarketStateProvider
from agent_server_new.app.context_builder import ContextBuilder
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
        allowance = risk_gate(RiskGateContext(global_regime="normal", cooldown_active=False))
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
                    "reasons": [*list(hpg.reasons), *list(sg.reasons)],
                },
                risk_gate={
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
                tags=["decision_trace"],
            )
            await self._recorder.record_agent_output(event.event_id, "decision_trace", trace.to_dict())

        if self._symbol_memory_recorder is not None:
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
        "confidence": dict(decision_confidence),
        "cross_horizon_policy": dict(cross_horizon or {}),
        "risk_hints": {
            "agent_action_hint": str(plan.action or "hold"),
            "agent_notes": str(plan.notes or ""),
            "decision_confidence": dict(decision_confidence),
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
    """保留：当未来 provider 直接返回 MSL dict 时，可在此处统一解析。"""

    if isinstance(d.get("market_regime"), dict):
        mr = d.get("market_regime") or {}
        ls = d.get("liquidity_state") or {}
        ps = d.get("positioning_state") or {}
        vs = d.get("volatility_state") or {}
        rs = d.get("risk_state") or {}
        st = d.get("market_structure_state") or d.get("structure_state") or {}
        kl = d.get("key_levels") or {}
        return MarketStateMSL(
            version=int(d.get("version") or 1),
            timestamp=str(d.get("timestamp") or ""),
            symbol=str(d.get("symbol") or ""),
            market_regime=MarketRegime(
                trend=str(mr.get("trend") or "unknown"),  # type: ignore[arg-type]
                phase=str(mr.get("phase") or "unknown"),  # type: ignore[arg-type]
                timeframe_alignment=str(mr.get("timeframe_alignment") or "unknown"),  # type: ignore[arg-type]
                strength=float(mr.get("strength") or 0.0),
            ),
            liquidity=LiquidityState(
                dominant_pressure=str(ls.get("dominant_pressure") or "unknown"),  # type: ignore[arg-type]
                liquidity_risk=str(ls.get("liquidity_risk") or "unknown"),  # type: ignore[arg-type]
                orderbook_bias=str(ls.get("orderbook_bias") or "unknown"),  # type: ignore[arg-type]
                liquidation_proximity=str(ls.get("liquidation_proximity") or "unknown"),  # type: ignore[arg-type]
            ),
            positioning=PositioningState(
                crowding=str(ps.get("crowding") or "unknown"),  # type: ignore[arg-type]
                whale_bias=str(ps.get("whale_bias") or "unknown"),  # type: ignore[arg-type]
                retail_bias=str(ps.get("retail_bias") or "unknown"),  # type: ignore[arg-type]
                oi_trend=str(ps.get("oi_trend") or "unknown"),  # type: ignore[arg-type]
            ),
            volatility=VolatilityState(
                volatility_regime=str(vs.get("volatility_regime") or "unknown"),  # type: ignore[arg-type]
                expansion_risk=str(vs.get("expansion_risk") or "unknown"),  # type: ignore[arg-type]
                volatility_direction=str(vs.get("volatility_direction") or "unknown"),  # type: ignore[arg-type]
            ),
            risk=RiskState(
                cascade_risk=str(rs.get("cascade_risk") or "unknown"),  # type: ignore[arg-type]
                squeeze_probability=str(rs.get("squeeze_probability") or "unknown"),  # type: ignore[arg-type]
                reversal_risk=str(rs.get("reversal_risk") or "unknown"),  # type: ignore[arg-type]
            ),
            market_structure=StructureState(
                support_strength=str(st.get("support_strength") or "unknown"),  # type: ignore[arg-type]
                resistance_strength=str(st.get("resistance_strength") or "unknown"),  # type: ignore[arg-type]
                range_state=str(st.get("range_state") or "unknown"),  # type: ignore[arg-type]
                trend_structure=str(st.get("trend_structure") or "unknown"),  # type: ignore[arg-type]
            ),
            key_levels=KeyLevels(
                major_support=[float(x) for x in list(kl.get("major_support") or []) if x is not None],
                major_resistance=[float(x) for x in list(kl.get("major_resistance") or []) if x is not None],
                liquidation_clusters=[float(x) for x in list(kl.get("liquidation_clusters") or []) if x is not None],
            ),
            anomalies=[str(x) for x in list(d.get("anomalies") or []) if x],
            summary=str(d.get("summary") or ""),
            evidence=dict(d.get("evidence") or {}),
        )

    return MarketStateMSL(
        version=1,
        timestamp="",
        symbol=str(d.get("symbol") or ""),
        market_regime=MarketRegime(trend="unknown", phase="unknown", timeframe_alignment="unknown", strength=0.0),
        liquidity=LiquidityState(dominant_pressure="unknown", liquidity_risk="unknown", orderbook_bias="unknown", liquidation_proximity="unknown"),
        positioning=PositioningState(crowding="unknown", whale_bias="unknown", retail_bias="unknown", oi_trend="unknown"),
        volatility=VolatilityState(volatility_regime="unknown", expansion_risk="unknown", volatility_direction="unknown"),
        risk=RiskState(cascade_risk="unknown", squeeze_probability="unknown", reversal_risk="unknown"),
        market_structure=StructureState(support_strength="unknown", resistance_strength="unknown", range_state="unknown", trend_structure="unknown"),
        key_levels=KeyLevels(),
        anomalies=[],
        summary="",
        evidence=dict(d.get("evidence") or {}),
    )
