from __future__ import annotations

from typing import Any, Dict

from execution_service.domain.contracts import DecisionIntent, ExecutionResult
from execution_service.domain.risk_rules import RiskContext, evaluate_risk_rules


class ExecutionDecisionEngine:
    """执行层确定性裁决器。"""

    @staticmethod
    def decide(
        decision: DecisionIntent,
        *,
        position_state: Dict[str, Any],
        account_state: Dict[str, Any],
        risk_policy: Dict[str, Any],
    ) -> ExecutionResult:
        rule_outcome = evaluate_risk_rules(
            decision,
            RiskContext(
                position_state=position_state,
                account_state=account_state,
                risk_policy=risk_policy,
            ),
        )
        return ExecutionResult.from_dict(
            {
                "decision_id": decision.decision_id,
                "execution_action": rule_outcome["execution_action"],
                "reject_reason": rule_outcome["reject_reason"],
                "applied_risk_rules": rule_outcome["applied_risk_rules"],
                "signal_result": rule_outcome.get("signal_result"),
                "notes": rule_outcome["notes"],
            }
        )
