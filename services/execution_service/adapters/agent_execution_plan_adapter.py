from __future__ import annotations

from typing import Any, Dict, Mapping


def adapt_agent_execution_plan_to_decision_intent(
    *,
    decision_id: str,
    exchange: str,
    symbol: str,
    plan: Mapping[str, Any],
    cross_horizon_policy: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """把 agent 输出的最小 ExecutionPlan 语义映射到 DecisionIntent v1。"""

    direction = str(plan.get("direction", "none")).strip().lower()
    confidence = plan.get("decision_confidence") or plan.get("confidence") or {"level": "low", "score": 0.0}
    if not isinstance(confidence, dict):
        confidence = {"level": "low", "score": 0.0}

    # execution_action 语义用于保留 agent 的动作建议，不作为硬裁决依据。
    agent_action = str(plan.get("action", "hold")).strip().lower()
    risk_hints: Dict[str, Any] = {
        "agent_action_hint": agent_action,
        "decision_confidence": dict(confidence),
    }
    notes = str(plan.get("notes", "")).strip()
    if notes:
        risk_hints["agent_notes"] = notes

    return {
        "decision_id": decision_id,
        "exchange": exchange,
        "symbol": symbol,
        "direction_intent": direction if direction in {"long", "short", "none"} else "none",
        "confidence": confidence,
        "decision_confidence": dict(confidence),
        "cross_horizon_policy": dict(cross_horizon_policy or {}),
        "risk_hints": risk_hints,
    }
