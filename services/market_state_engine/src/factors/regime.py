from __future__ import annotations

from typing import Literal


def infer_direction_bias(price_direction: str) -> Literal["bullish", "bearish", "neutral", "unknown"]:
    if price_direction == "up":
        return "bullish"
    if price_direction == "down":
        return "bearish"
    if price_direction in ("flat", "neutral"):
        return "neutral"
    return "unknown"


def normalize_trend_strength(price_strength: str) -> str:
    if price_strength in ("strong", "medium", "weak"):
        return price_strength
    return "unknown"


def infer_horizon_alignment(
    short_direction: str,
    mid_direction: str,
    short_strength: str,
    mid_strength: str,
) -> Literal["aligned", "mixed", "conflict", "unknown"]:
    if not short_direction or not mid_direction:
        return "unknown"
    if short_direction == "flat" or mid_direction == "flat":
        return "mixed"
    if short_direction == mid_direction:
        if short_strength in ("strong", "medium") and mid_strength in ("strong", "medium"):
            return "aligned"
        return "mixed"
    return "conflict"


def infer_regime(short_context_label: str, mid_context_label: str, horizon_alignment: str) -> Literal["trend", "range", "transition", "breakdown", "unknown"]:
    blob = (short_context_label + " " + mid_context_label).lower()
    if "breakdown" in blob or "break" in blob:
        return "breakdown"
    if "range" in blob or "consolidation" in blob or "chop" in blob:
        return "range"
    if horizon_alignment == "conflict":
        return "transition"
    if "trend" in blob or "continuation" in blob or "directional" in blob:
        return "trend"
    return "unknown"


def infer_market_phase(
    regime: str,
    participant_behavior: str,
    crowding_out: str,
    volatility_state: str,
) -> Literal["expansion", "distribution", "contraction", "accumulation", "unknown"]:
    if regime == "trend" and participant_behavior == "adding_leverage" and volatility_state != "high":
        return "expansion"
    if crowding_out == "high" and volatility_state in ("high", "normal") and regime in ("trend", "transition"):
        return "distribution"
    if participant_behavior == "reducing_leverage" and regime in ("breakdown", "transition"):
        return "contraction"
    if regime == "range" and participant_behavior in ("unclear", "reducing_leverage") and volatility_state in ("low", "normal"):
        return "accumulation"
    return "unknown"


def infer_trend(direction_bias: str) -> Literal["bullish", "bearish", "sideways", "unknown"]:
    if direction_bias == "bullish":
        return "bullish"
    if direction_bias == "bearish":
        return "bearish"
    if direction_bias == "neutral":
        return "sideways"
    return "unknown"


def infer_phase(market_phase: str) -> Literal["impulse", "continuation", "exhaustion", "accumulation", "distribution", "unknown"]:
    if market_phase == "expansion":
        return "continuation"
    if market_phase == "distribution":
        return "distribution"
    if market_phase == "contraction":
        return "exhaustion"
    if market_phase == "accumulation":
        return "accumulation"
    return "unknown"


def infer_timeframe_alignment(horizon_alignment: str) -> Literal["aligned", "mixed", "conflicting", "unknown"]:
    if horizon_alignment == "aligned":
        return "aligned"
    if horizon_alignment == "mixed":
        return "mixed"
    if horizon_alignment == "conflict":
        return "conflicting"
    return "unknown"


def infer_strength(trend_strength: str, horizon_alignment: str, market_fragility: str) -> float:
    if trend_strength == "strong":
        strength = 0.78
    elif trend_strength == "medium":
        strength = 0.6
    elif trend_strength == "weak":
        strength = 0.42
    else:
        strength = 0.0
    if horizon_alignment == "conflict":
        strength = min(strength, 0.45)
    if market_fragility in ("medium", "high"):
        strength = min(strength, 0.55 if market_fragility == "medium" else 0.45)
    return float(strength)
