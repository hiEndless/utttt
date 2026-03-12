from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List

from services.market_state_engine.src.contracts import MarketStateMSL

from .contracts import ActionIntent, RulePlan, SignalVerdict
from .strategy_gate_reasons import (
    STRATEGY_GATE_REASON_DIRECTION_BIAS_MISMATCH,
    STRATEGY_GATE_REASON_FRAGILITY_HIGH_BLOCK_INCREASE,
    STRATEGY_GATE_REASON_HORIZON_CONFLICT,
    STRATEGY_GATE_REASON_LIQUIDITY_VACUUM,
    STRATEGY_GATE_REASON_SIGNAL_REJECTED,
    STRATEGY_GATE_REASON_SIGNAL_STALE,
    STRATEGY_GATE_REASON_TRANSITION_AND_UNCERTAIN,
)


@dataclass(frozen=True)
class StrategyGateResult:
    """策略门控：决定“是否值得进入风险与执行阶段”。"""

    allowed: bool
    reasons: List[str] = field(default_factory=list)


def strategy_gate(*, msl: MarketStateMSL, signal: SignalVerdict) -> StrategyGateResult:
    """兼容入口：保留旧签名。"""
    reasons: List[str] = []
    if signal.verdict == "reject":
        return StrategyGateResult(allowed=False, reasons=[STRATEGY_GATE_REASON_SIGNAL_REJECTED])
    if msl.horizon_alignment == "conflict":
        reasons.append(STRATEGY_GATE_REASON_HORIZON_CONFLICT)
    if msl.regime == "transition" and signal.verdict == "uncertain":
        reasons.append(STRATEGY_GATE_REASON_TRANSITION_AND_UNCERTAIN)
    anomalies = set([str(x) for x in list(msl.anomalies or []) if x])
    if "liquidity_vacuum" in anomalies or "orderbook_liquidity_vacuum" in anomalies:
        reasons.append(STRATEGY_GATE_REASON_LIQUIDITY_VACUUM)
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
    anomalies = set([str(x) for x in list(msl.anomalies or []) if x])

    signal_ts_ms = _extract_signal_event_ts_ms(signal_event)
    try:
        age_ms = int(msl.ts) - int(signal_ts_ms) if signal_ts_ms is not None else None
    except Exception:
        age_ms = None
    if age_ms is not None and age_ms > 10 * 60 * 1000:
        reasons.append(STRATEGY_GATE_REASON_SIGNAL_STALE)

    if intent.intent == "increase" and msl.market_fragility == "high":
        reasons.append(STRATEGY_GATE_REASON_FRAGILITY_HIGH_BLOCK_INCREASE)

    if intent.intent == "increase" and msl.direction_bias in ("bullish", "bearish") and signal.direction in ("long", "short"):
        if (msl.direction_bias == "bullish" and signal.direction == "short") or (msl.direction_bias == "bearish" and signal.direction == "long"):
            reasons.append(STRATEGY_GATE_REASON_DIRECTION_BIAS_MISMATCH)

    if intent.intent in ("increase", "hold") and ("liquidity_vacuum" in anomalies or "orderbook_liquidity_vacuum" in anomalies):
        reasons.append(STRATEGY_GATE_REASON_LIQUIDITY_VACUUM)

    if intent.intent == "increase" and msl.horizon_alignment == "conflict":
        reasons.append(STRATEGY_GATE_REASON_HORIZON_CONFLICT)

    if reasons:
        return StrategyGateResult(allowed=False, reasons=reasons)
    return StrategyGateResult(allowed=True, reasons=[])


def _extract_signal_event_ts_ms(signal_event: Dict[str, Any]) -> int | None:
    for key in ("event_ts_ms", "ts_ms", "timestamp_ms", "ts", "generated_at_ms"):
        raw = signal_event.get(key)
        if raw is None:
            continue
        try:
            return int(raw)
        except Exception:
            continue
    raw_ts = signal_event.get("timestamp")
    if raw_ts is None:
        return None
    s = str(raw_ts or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return None
