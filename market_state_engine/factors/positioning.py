from __future__ import annotations

from typing import Literal


def infer_participant_behavior(delta_oi_pct: float, oi_velocity: str) -> Literal["adding_leverage", "reducing_leverage", "rotation", "unclear", "unknown"]:
    if abs(delta_oi_pct) < 0.003 or oi_velocity not in ("medium", "high"):
        return "unclear"
    if delta_oi_pct > 0:
        return "adding_leverage"
    return "reducing_leverage"


def infer_oi_trend(oi_trend_raw: str) -> Literal["expanding", "contracting", "flat", "unknown"]:
    if oi_trend_raw in ("expanding", "contracting", "flat"):
        return oi_trend_raw  # type: ignore[return-value]
    return "unknown"


def infer_crowding(crowding_out: str, direction_bias: str) -> Literal["crowded_long", "crowded_short", "balanced", "unknown"]:
    if crowding_out == "high" and direction_bias == "bullish":
        return "crowded_long"
    if crowding_out == "high" and direction_bias == "bearish":
        return "crowded_short"
    if crowding_out in ("normal", "low"):
        return "balanced"
    return "unknown"
