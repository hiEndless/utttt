from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from services.market_state_engine.src.contracts import MarketStateMSL

from services.agent_server_new.domain.contracts import ActionIntent, Confidence, ExecutionPlan, RiskAllowance, RulePlan, SignalDecision
from services.agent_server_new.domain.execution_planner import build_execution_plan
from services.agent_server_new.domain.horizon_policy_gate import horizon_policy_gate
from services.agent_server_new.domain.intent_resolver import resolve_intent
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
from services.agent_server_new.domain.strategy_gate import strategy_gate_v2


@dataclass(frozen=True)
class PipelineCompatState:
    intent: ActionIntent
    rule_plan: RulePlan
    hpg_allowed: bool
    hpg_reasons: list[str]
    sg_allowed: bool
    sg_reasons: list[str]
    risk_ctx: RiskGateContext
    risk_ctx_reasons: list[str]
    allowance: RiskAllowance
    plan: ExecutionPlan


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


def build_pipeline_compat_state(
    *,
    legacy_pipeline_enabled: bool,
    signal: Any,
    msl: MarketStateMSL,
    position_context: Dict[str, Any],
    active_events: list[Dict[str, Any]],
    signal_event: Dict[str, Any],
    cross_horizon: Dict[str, str],
    horizon_policy_config: Dict[str, Any],
    resolve_intent_fn: Callable[..., Any] = resolve_intent,
    build_rule_plan_fn: Callable[..., Any] = build_rule_plan,
    horizon_policy_gate_fn: Callable[..., Any] = horizon_policy_gate,
    strategy_gate_fn: Callable[..., Any] = strategy_gate_v2,
    derive_risk_gate_context_fn: Callable[..., tuple[RiskGateContext, list[str]]] = _derive_risk_gate_context,
    risk_gate_fn: Callable[..., RiskAllowance] = risk_gate,
    build_execution_plan_fn: Callable[..., ExecutionPlan] = build_execution_plan,
) -> PipelineCompatState:
    # 中文注释：legacy 决策链路集中为兼容层，workflow 主干只消费统一 state。
    if legacy_pipeline_enabled:
        intent = resolve_intent_fn(signal=signal, msl=msl, position_context=position_context)
        rule_plan = build_rule_plan_fn(intent=intent, msl=msl, position_context=position_context)
        hpg = horizon_policy_gate_fn(
            suggested_policy=str(cross_horizon.get("suggested_policy") or "no_action"),
            policy_reason=str(cross_horizon.get("policy_reason") or "insufficient_evidence"),
            intent=str(intent.intent),
            config=horizon_policy_config,
        )
        sg = strategy_gate_fn(
            msl=msl,
            signal=signal,
            intent=intent,
            rule_plan=rule_plan,
            position_context=position_context,
            signal_event=signal_event,
        )
        risk_ctx, risk_ctx_reasons = derive_risk_gate_context_fn(
            msl=msl,
            position_context=position_context,
            active_events=active_events,
        )
        allowance = risk_gate_fn(risk_ctx)
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
            plan = build_execution_plan_fn(rule_plan=rule_plan, allowance=allowance, risk_constraints={})
        return PipelineCompatState(
            intent=intent,
            rule_plan=rule_plan,
            hpg_allowed=hpg_allowed,
            hpg_reasons=hpg_reasons,
            sg_allowed=sg_allowed,
            sg_reasons=sg_reasons,
            risk_ctx=risk_ctx,
            risk_ctx_reasons=risk_ctx_reasons,
            allowance=allowance,
            plan=plan,
        )

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
    risk_ctx = RiskGateContext(global_regime="normal", cooldown_active=False)
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
    return PipelineCompatState(
        intent=intent,
        rule_plan=rule_plan,
        hpg_allowed=True,
        hpg_reasons=["legacy_pipeline_disabled"],
        sg_allowed=True,
        sg_reasons=["legacy_pipeline_disabled"],
        risk_ctx=risk_ctx,
        risk_ctx_reasons=["legacy_pipeline_disabled"],
        allowance=allowance,
        plan=plan,
    )


def build_legacy_stage_outputs(
    *,
    state: PipelineCompatState,
    cross_horizon: Dict[str, str],
) -> list[tuple[str, Dict[str, Any]]]:
    return [
        (
            "intent_resolver",
            {
                "intent": state.intent.intent,
                "direction": state.intent.direction,
                "confidence": {
                    "level": state.intent.confidence.level,
                    "score": state.intent.confidence.score,
                },
                "reasons": list(state.intent.reasons),
                "notes": state.intent.notes,
            },
        ),
        (
            "rule_planner",
            {
                "intent": {
                    "intent": state.rule_plan.intent.intent,
                    "direction": state.rule_plan.intent.direction,
                    "confidence": {
                        "level": state.rule_plan.intent.confidence.level,
                        "score": state.rule_plan.intent.confidence.score,
                    },
                },
                "sizing": dict(state.rule_plan.sizing or {}),
                "reasons": list(state.rule_plan.reasons),
                "notes": state.rule_plan.notes,
            },
        ),
        (
            "horizon_policy_gate",
            {
                "allowed": bool(state.hpg_allowed),
                "reasons": list(state.hpg_reasons),
                "cross_horizon": dict(cross_horizon or {}),
            },
        ),
        (
            "strategy_gate",
            {
                "allowed": bool(state.sg_allowed),
                "reasons": list(state.sg_reasons),
            },
        ),
        (
            "execution_planner",
            {
                "action": state.plan.action,
                "direction": state.plan.direction,
                "sizing": dict(state.plan.sizing or {}),
                "allowance": {
                    "allow_open": state.plan.allowance.allow_open,
                    "allow_add": state.plan.allowance.allow_add,
                    "allow_reduce": state.plan.allowance.allow_reduce,
                    "allow_exit": state.plan.allowance.allow_exit,
                    "reasons": list(state.plan.allowance.reasons),
                },
                "confidence": {
                    "level": state.plan.confidence.level,
                    "score": state.plan.confidence.score,
                },
                "notes": state.plan.notes,
            },
        ),
    ]


def build_decision_trace_legacy_sections(
    *,
    state: PipelineCompatState,
) -> Dict[str, Dict[str, Any]]:
    return {
        "intent": {
            "intent": state.intent.intent,
            "direction": state.intent.direction,
            "confidence": {
                "level": state.intent.confidence.level,
                "score": state.intent.confidence.score,
            },
            "reasons": list(state.intent.reasons),
        },
        "rule_plan": {
            "intent": {
                "intent": state.rule_plan.intent.intent,
                "direction": state.rule_plan.intent.direction,
                "confidence": {
                    "level": state.rule_plan.intent.confidence.level,
                    "score": state.rule_plan.intent.confidence.score,
                },
            },
            "sizing": dict(state.rule_plan.sizing or {}),
            "reasons": list(state.rule_plan.reasons),
        },
        "strategy_gate_result": {
            "allowed": bool(state.hpg_allowed and state.sg_allowed),
            "horizon_reasons": list(state.hpg_reasons),
            "strategy_reasons": list(state.sg_reasons),
            "reasons": [*list(state.hpg_reasons), *list(state.sg_reasons)],
        },
        "risk_gate": {
            "global_regime": state.risk_ctx.global_regime,
            "cooldown_active": bool(state.risk_ctx.cooldown_active),
            "regime_sources": list(state.risk_ctx_reasons),
            "allow_open": state.allowance.allow_open,
            "allow_add": state.allowance.allow_add,
            "allow_reduce": state.allowance.allow_reduce,
            "allow_exit": state.allowance.allow_exit,
            "reasons": list(state.allowance.reasons),
        },
    }


def build_symbol_memory_legacy_sections(
    *,
    state: PipelineCompatState,
    cross_horizon: Dict[str, str],
) -> Dict[str, Dict[str, Any]]:
    return {
        "cross_horizon_policy": dict(cross_horizon or {}),
        "intent": {
            "intent": state.intent.intent,
            "direction": state.intent.direction,
            "confidence": {
                "level": state.intent.confidence.level,
                "score": state.intent.confidence.score,
            },
            "reasons": list(state.intent.reasons),
        },
        "plan": {
            "action": state.plan.action,
            "direction": state.plan.direction,
            "notes": state.plan.notes,
        },
    }


def build_execution_decision_payload(
    *,
    default_decision_id: str,
    default_exchange: str,
    default_symbol: str,
    signal_decision: SignalDecision,
    plan: ExecutionPlan,
    pipeline_mode: str,
    cross_horizon: Dict[str, str],
    prompt_config_source: str = "",
    prompt_config_version: str = "",
    ai_adaptive_enabled: bool = False,
    ai_adaptive_mode: str = "observe",
) -> Dict[str, Any]:
    normalized_mode = str(pipeline_mode or "legacy").strip().lower()
    decision_confidence_source = "agent_execution_plan"
    decision_confidence = {
        "level": str(plan.confidence.level or "low"),
        "score": float(plan.confidence.score or 0.0),
    }
    if normalized_mode == "minimal":
        signal_conf = signal_decision.confidence
        decision_confidence = {
            "level": str(signal_conf.level or "low"),
            "score": float(signal_conf.score or 0.0),
        }
        decision_confidence_source = "agent_signal_decision"
    agent_action_hint = str(plan.action or "hold").strip().lower() or "hold"
    if normalized_mode == "minimal":
        verdict = str(signal_decision.signal_verdict or "uncertain").strip().lower()
        direction = str(signal_decision.signal_direction or "none").strip().lower()
        agent_action_hint = "add" if verdict == "accept" and direction in {"long", "short"} else "hold"
    payload = {
        "decision_id": str(signal_decision.decision_id or default_decision_id),
        "exchange": str(signal_decision.exchange or default_exchange),
        "symbol": str(signal_decision.symbol or default_symbol),
        "direction_intent": str(signal_decision.signal_direction or "none"),
        "decision_confidence": dict(decision_confidence),
        "cross_horizon_policy": dict(cross_horizon or {}),
        "risk_hints": {
            "agent_action_hint": agent_action_hint,
            "agent_notes": str(plan.notes or ""),
            "decision_confidence": dict(decision_confidence),
            "decision_confidence_source": decision_confidence_source,
            "decision_agent_key": str(signal_decision.decision_agent_key or ""),
            "decision_mode": str(signal_decision.decision_mode or "rule"),
            "llm_parse_status": str(signal_decision.llm_parse_status or ""),
            "prompt_config_source": str(prompt_config_source or ""),
            "prompt_config_version": str(prompt_config_version or ""),
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


def build_signal_decision_from_signal(
    *,
    decision_id: str,
    exchange: str,
    symbol: str,
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
    conf = getattr(signal, "confidence", None)
    raw_score = float(getattr(conf, "score", 0.0) or 0.0)
    reliability_score = max(0.0, min(1.0, raw_score))
    reasons = [str(x) for x in list(getattr(signal, "invalidation_reasons", []) or []) if str(x)]
    normalized_conf = Confidence(level="low", score=0.0) if conf is None else conf
    return SignalDecision(
        decision_id=str(decision_id or ""),
        exchange=str(exchange or ""),
        symbol=str(symbol or ""),
        decision_agent_key=str(decision_agent_key or "generic"),
        decision_mode=mode,  # type: ignore[arg-type]
        llm_parse_status=parse_status,  # type: ignore[arg-type]
        signal_direction=direction,  # type: ignore[arg-type]
        signal_verdict=verdict,  # type: ignore[arg-type]
        confidence=normalized_conf,  # type: ignore[arg-type]
        reliability_score=reliability_score,
        reasons=reasons,
        evidence_refs=[],
        llm_observation=dict(llm_observation or {}),
    )


def build_workflow_bridge_payload(
    *,
    state: PipelineCompatState,
    signal_decision: SignalDecision,
    pipeline_mode: str = "minimal",
) -> Dict[str, Any]:
    mode = str(pipeline_mode or "minimal").strip().lower() or "minimal"
    return {
        "pipeline_mode": mode,
        "notes": str(state.plan.notes or ""),
        "decision": {
            "decision_agent_key": signal_decision.decision_agent_key,
            "decision_mode": signal_decision.decision_mode,
            "llm_parse_status": signal_decision.llm_parse_status,
            "signal_verdict": signal_decision.signal_verdict,
            "signal_direction": signal_decision.signal_direction,
            "reliability_score": signal_decision.reliability_score,
        },
        "execution_plan": {
            "action": state.plan.action,
            "direction": state.plan.direction,
            "confidence": {
                "level": state.plan.confidence.level,
                "score": state.plan.confidence.score,
            },
            "notes": state.plan.notes,
        },
    }
