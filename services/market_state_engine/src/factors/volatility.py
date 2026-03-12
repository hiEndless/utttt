from __future__ import annotations

from typing import Literal


def infer_volatility_state(volatility_raw: str, participant_stability: str) -> Literal["low", "normal", "high", "unknown"]:
    if volatility_raw == "medium":
        return "normal"
    if volatility_raw in ("low", "high"):
        return volatility_raw  # type: ignore[return-value]
    if participant_stability == "volatile":
        return "high"
    if participant_stability == "stable":
        return "low"
    if participant_stability:
        return "normal"
    return "unknown"


def infer_expansion_risk(volatility_state: str, participant_behavior: str) -> Literal["expanding", "compressing", "unknown"]:
    if volatility_state == "low":
        return "compressing"
    if volatility_state == "high":
        return "expanding"
    if participant_behavior == "adding_leverage":
        return "expanding"
    return "unknown"


def infer_volatility_direction(direction_bias: str) -> Literal["upside", "downside", "neutral", "unknown"]:
    if direction_bias == "bullish":
        return "upside"
    if direction_bias == "bearish":
        return "downside"
    if direction_bias == "neutral":
        return "neutral"
    return "unknown"
