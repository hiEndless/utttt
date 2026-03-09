from __future__ import annotations

from typing import List, Literal


def build_risk_flags(
    *,
    liquidity_state: str,
    crowding_out: str,
    oi_flags: List[str],
) -> List[str]:
    risk_flags: List[str] = []
    if liquidity_state == "thin":
        risk_flags.append("liquidity_vacuum")
    if crowding_out == "high":
        risk_flags.append("crowding")
    if any(x in {"possible_liquidation_or_unwind", "fragile_leverage_build"} for x in oi_flags):
        risk_flags.append("liquidation_cluster")
    risk_flags.extend(oi_flags)
    return sorted(set([x for x in risk_flags if x]))


def infer_market_fragility(
    *,
    anomaly_flags: List[str],
    liquidity_state: str,
    volatility_state: str,
    crowding_out: str,
) -> Literal["low", "medium", "high", "unknown"]:
    fragility_score = 0
    if "orderbook_liquidity_vacuum" in set(anomaly_flags) or liquidity_state == "thin":
        fragility_score += 2
    if "liquidation_cluster" in set(anomaly_flags) or "leverage_extreme" in set(anomaly_flags):
        fragility_score += 2
    if volatility_state == "high":
        fragility_score += 1
    if crowding_out == "high":
        fragility_score += 1
    if fragility_score >= 4:
        return "high"
    if fragility_score >= 2:
        return "medium"
    if fragility_score >= 0:
        return "low"
    return "unknown"


def infer_cascade_risk(market_fragility: str) -> Literal["high", "medium", "low", "unknown"]:
    if market_fragility in ("low", "medium", "high"):
        return market_fragility  # type: ignore[return-value]
    return "unknown"


def infer_squeeze_probability(
    *,
    liquidity_risk: str,
    anomaly_flags: List[str],
    crowding_out: str,
    volatility_state: str,
) -> Literal["high", "medium", "low", "unknown"]:
    squeeze_score = 0
    if liquidity_risk in ("short_squeeze", "long_squeeze"):
        squeeze_score += 2
    if "crowding_extreme" in set(anomaly_flags):
        squeeze_score += 2
    if "leverage_extreme" in set(anomaly_flags):
        squeeze_score += 2
    if crowding_out == "high":
        squeeze_score += 1
    if volatility_state == "high":
        squeeze_score += 1
    if squeeze_score >= 4:
        return "high"
    if squeeze_score >= 2:
        return "medium"
    return "low"


def infer_reversal_risk(
    *,
    horizon_alignment: str,
    phase: str,
    volatility_state: str,
) -> Literal["high", "medium", "low", "unknown"]:
    reversal_score = 0
    if horizon_alignment == "conflict":
        reversal_score += 2
    if phase in ("distribution", "exhaustion"):
        reversal_score += 1
    if volatility_state == "high":
        reversal_score += 1
    if reversal_score >= 3:
        return "high"
    if reversal_score >= 2:
        return "medium"
    return "low"
