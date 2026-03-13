from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from services.market_state_engine.src.contracts import MarketStateMSL

from services.agent_server_new.domain.contracts import ActionIntent, ExecutionPlan, RiskAllowance, RulePlan
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
