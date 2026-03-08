from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from market_state_engine.contracts import MarketStateMSL

from .contracts import ActionIntent, RulePlan, SignalVerdict


@dataclass(frozen=True)
class StrategyGateResult:
    """策略门控：决定“是否值得进入风险与执行阶段”。"""

    allowed: bool
    reasons: List[str] = field(default_factory=list)


def strategy_gate(*, msl: MarketStateMSL, signal: SignalVerdict) -> StrategyGateResult:
    """兼容入口：保留旧签名。"""
    reasons: List[str] = []
    if signal.verdict == "reject":
        return StrategyGateResult(allowed=False, reasons=["signal_rejected"])
    if msl.horizon_alignment == "conflict":
        reasons.append("horizon_conflict")
    if msl.regime == "transition" and signal.verdict == "uncertain":
        reasons.append("transition_and_uncertain")
    if "liquidity_vacuum" in set(msl.risk_flags or []):
        reasons.append("liquidity_vacuum")
    if reasons:
        return StrategyGateResult(allowed=False, reasons=reasons)
    return StrategyGateResult(allowed=True, reasons=[])


def strategy_gate_v2(
    *,
    msl: MarketStateMSL,
    signal: SignalVerdict,
    intent: ActionIntent,
    rule_plan: RulePlan,
    position_context: Dict[str, Any],
    signal_event: Dict[str, Any],
) -> StrategyGateResult:
    """策略门控（v2）：检查 freshness、regime mismatch、以及规则计划与市场语境冲突。"""

    reasons: List[str] = []

    ts = signal_event.get("ts") or signal_event.get("timestamp") or signal_event.get("timestamp_ms")
    try:
        age_ms = int(msl.ts) - int(ts) if ts is not None else None
    except Exception:
        age_ms = None
    if age_ms is not None and age_ms > 10 * 60 * 1000:
        reasons.append("signal_stale")

    if intent.intent == "increase" and msl.market_fragility == "high":
        reasons.append("fragility_high_block_increase")

    if intent.intent == "increase" and msl.direction_bias in ("bullish", "bearish") and signal.direction in ("long", "short"):
        if (msl.direction_bias == "bullish" and signal.direction == "short") or (msl.direction_bias == "bearish" and signal.direction == "long"):
            reasons.append("direction_bias_mismatch")

    if intent.intent in ("increase", "hold") and "liquidity_vacuum" in set(msl.risk_flags or []):
        reasons.append("liquidity_vacuum")

    if intent.intent == "increase" and msl.horizon_alignment == "conflict":
        reasons.append("horizon_conflict")

    if reasons:
        return StrategyGateResult(allowed=False, reasons=reasons)
    return StrategyGateResult(allowed=True, reasons=[])
