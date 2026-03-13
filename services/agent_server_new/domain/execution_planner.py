from __future__ import annotations

"""Deprecated legacy domain module.

This module is kept only for historical compatibility and offline replay reference.
TradeEventWorkflow minimal main path must not import or call this module.
"""

from typing import Any, Dict, Optional

from .contracts import Confidence, ExecutionPlan, RiskAllowance, RulePlan


def _intent_to_risk_action(intent: str) -> str:
    if intent == "increase":
        return "add"
    if intent == "decrease":
        return "reduce"
    if intent == "close":
        return "exit"
    if intent == "skip":
        return "skip"
    return "hold"


def build_execution_plan(
    *,
    rule_plan: RulePlan,
    allowance: RiskAllowance,
    risk_constraints: Optional[Dict[str, Any]] = None,
) -> ExecutionPlan:
    """ExecutionPlanner：RulePlan + 风险约束 -> ExecutionPlan（不依赖 LLM）。"""

    risk_constraints = dict(risk_constraints or {})
    intent = rule_plan.intent
    action = _intent_to_risk_action(intent.intent)
    direction = intent.direction

    if action == "add" and not allowance.allow_add:
        return ExecutionPlan(
            action="hold",
            direction=direction,
            allowance=allowance,
            confidence=Confidence(level="low", score=min(intent.confidence.score, 0.45)),
            sizing=None,
            notes="执行规划：不允许加仓，降级为观望。",
        )
    if action == "reduce" and not allowance.allow_reduce:
        return ExecutionPlan(
            action="hold",
            direction="none",
            allowance=allowance,
            confidence=Confidence(level="low", score=min(intent.confidence.score, 0.45)),
            sizing=None,
            notes="执行规划：不允许减仓，降级为观望。",
        )
    if action == "exit" and not allowance.allow_exit:
        return ExecutionPlan(
            action="hold",
            direction="none",
            allowance=allowance,
            confidence=Confidence(level="low", score=min(intent.confidence.score, 0.45)),
            sizing=None,
            notes="执行规划：不允许平仓，降级为观望。",
        )

    merged_sizing: Optional[Dict[str, Any]] = dict(rule_plan.sizing or {})
    for k, v in dict(risk_constraints or {}).items():
        merged_sizing.setdefault(str(k), v)

    return ExecutionPlan(
        action=action,  # type: ignore[arg-type]
        direction=direction,
        allowance=allowance,
        confidence=intent.confidence,
        sizing=merged_sizing,
        notes=rule_plan.notes or intent.notes,
    )
