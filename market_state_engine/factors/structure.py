from __future__ import annotations

from typing import Literal


def infer_range_state(regime: str) -> Literal["breakout", "range", "breakdown", "unknown"]:
    if regime == "range":
        return "range"
    if regime == "breakdown":
        return "breakdown"
    if regime == "trend":
        return "breakout"
    return "unknown"


def infer_trend_structure(direction_bias: str) -> Literal["hh_hl", "lh_ll", "mixed", "unknown"]:
    if direction_bias == "bullish":
        return "hh_hl"
    if direction_bias == "bearish":
        return "lh_ll"
    if direction_bias == "neutral":
        return "mixed"
    return "unknown"
