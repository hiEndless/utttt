from __future__ import annotations

from typing import Literal


def infer_liquidity_state(liquidity_vacuum: bool, stability: str) -> Literal["deep", "normal", "thin", "unknown"]:
    if liquidity_vacuum:
        return "thin"
    if stability == "fragile":
        return "thin"
    if stability == "stable":
        return "normal"
    if stability:
        return "normal"
    return "unknown"


def infer_dominant_pressure(direction_bias: str) -> Literal["buyers", "sellers", "balanced", "unknown"]:
    if direction_bias == "bullish":
        return "buyers"
    if direction_bias == "bearish":
        return "sellers"
    if direction_bias == "neutral":
        return "balanced"
    return "unknown"


def infer_orderbook_bias(stability: str) -> Literal["bid_heavy", "ask_heavy", "neutral", "unknown"]:
    if stability in ("stable", "fragile"):
        return "neutral"
    if stability:
        return "neutral"
    return "unknown"


def infer_liquidity_risk(squeeze_flag: bool, direction_bias: str) -> Literal["short_squeeze", "long_squeeze", "neutral", "unknown"]:
    if squeeze_flag and direction_bias == "bullish":
        return "short_squeeze"
    if squeeze_flag and direction_bias == "bearish":
        return "long_squeeze"
    if squeeze_flag:
        return "unknown"
    return "neutral"


def infer_liquidation_proximity(squeeze_flag: bool) -> Literal["above", "below", "both", "none", "unknown"]:
    if squeeze_flag:
        return "unknown"
    return "none"
