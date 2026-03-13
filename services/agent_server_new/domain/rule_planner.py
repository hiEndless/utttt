from __future__ import annotations

"""Deprecated legacy domain module.

This module is kept only for historical compatibility and offline replay reference.
TradeEventWorkflow minimal main path must not import or call this module.
"""

from typing import Any, Dict, List

from services.market_state_engine.src.contracts import MarketStateMSL

from .contracts import ActionIntent, RulePlan


def build_rule_plan(
    *,
    intent: ActionIntent,
    msl: MarketStateMSL,
    position_context: Dict[str, Any],
) -> RulePlan:
    """RulePlanner：ActionIntent + PositionContext + MSL -> RulePlan（主要负责 sizing 规则化）。"""

    reasons: List[str] = []
    sizing: Dict[str, Any] = {}

    has_position = bool((position_context or {}).get("has_position") is True)

    if intent.intent == "increase":
        base = 0.1
        if intent.confidence.level == "high":
            base = 0.15
        elif intent.confidence.level == "low":
            base = 0.07

        if msl.volatility.volatility_regime == "high":
            base *= 0.6
            reasons.append("downsize_high_volatility")
        if msl.market_fragility == "medium":
            base *= 0.7
            reasons.append("downsize_fragility_medium")
        if msl.market_fragility == "high":
            base *= 0.4
            reasons.append("downsize_fragility_high")

        sizing = {"mode": "ratio", "order_size_ratio": round(float(base), 4), "entry_type": "market"}
        return RulePlan(intent=intent, sizing=sizing, reasons=reasons, notes=intent.notes)

    if intent.intent == "decrease":
        ratio = 0.25
        if msl.market_fragility == "high" or msl.volatility.volatility_regime == "high":
            ratio = 0.4
            reasons.append("increase_exit_ratio_on_fragility_or_vol")
        sizing = {"mode": "ratio", "partial_exit_ratio": float(ratio), "entry_type": "market"}
        return RulePlan(intent=intent, sizing=sizing, reasons=reasons, notes=intent.notes)

    if intent.intent == "close":
        sizing = {"mode": "full", "entry_type": "market"}
        return RulePlan(intent=intent, sizing=sizing, reasons=["close_intent"], notes=intent.notes)

    if intent.intent == "hold":
        if has_position and msl.market_fragility == "high":
            sizing = {"mode": "ratio", "partial_exit_ratio": 0.15, "entry_type": "market"}
            reasons.append("light_reduce_on_high_fragility")
        return RulePlan(intent=intent, sizing=sizing, reasons=reasons, notes=intent.notes)

    return RulePlan(intent=intent, sizing={}, reasons=["skip"], notes=intent.notes)
