"""execution_service domain layer."""
"""execution_service domain layer."""

from .contracts import DecisionConfidence, DecisionIntent, ExecutionResult
from .decision_engine import ExecutionDecisionEngine
from .risk_rules import RiskContext, evaluate_risk_rules
from .reconcile_codes import (
    RECONCILE_REASON_CODES,
    RECONCILE_REASON_IN_PROGRESS,
    RECONCILE_REASON_NON_RETRYABLE_ERROR,
    RECONCILE_REASON_RETRY_EXHAUSTED,
)
from .reconcile_statuses import (
    RECONCILE_STATUSES,
    RECONCILE_STATUS_SUBMITTED,
    RECONCILE_STATUS_FILLED,
    RECONCILE_STATUS_CANCELED,
    RECONCILE_STATUS_REJECTED,
    RECONCILE_STATUS_FAILED,
)
from .retry_meta import RETRY_META_STATUSES, RETRY_META_STATUS_FAILED, RETRY_META_STATUS_OK
from .risk_check_codes import RISK_CHECK_CODES
from .risk_check_meta import RISK_CHECK_SCOPES, RISK_CHECK_STATUSES
from .risk_check_messages import (
    RISK_MSG_ACCOUNT_AVAILABLE_BALANCE,
    RISK_MSG_ACCOUNT_DRAWDOWN,
    RISK_MSG_ACCOUNT_MARGIN_RATIO_LIMIT,
    RISK_MSG_ACCOUNT_NOTIONAL_LIMIT,
    RISK_MSG_LONG_LEG_POSITION_LIMIT,
    RISK_MSG_SHORT_LEG_POSITION_LIMIT,
    RISK_MSG_SYMBOL_EXPOSURE_RATIO,
)
from .risk_check_builder import build_risk_checks
from .risk_result_builder import build_risk_decision_result

__all__ = [
    "DecisionConfidence",
    "DecisionIntent",
    "ExecutionResult",
    "ExecutionDecisionEngine",
    "RiskContext",
    "evaluate_risk_rules",
    "RECONCILE_REASON_CODES",
    "RECONCILE_REASON_IN_PROGRESS",
    "RECONCILE_REASON_NON_RETRYABLE_ERROR",
    "RECONCILE_REASON_RETRY_EXHAUSTED",
    "RECONCILE_STATUSES",
    "RECONCILE_STATUS_SUBMITTED",
    "RECONCILE_STATUS_FILLED",
    "RECONCILE_STATUS_CANCELED",
    "RECONCILE_STATUS_REJECTED",
    "RECONCILE_STATUS_FAILED",
    "RETRY_META_STATUSES",
    "RETRY_META_STATUS_FAILED",
    "RETRY_META_STATUS_OK",
    "RISK_CHECK_CODES",
    "RISK_CHECK_SCOPES",
    "RISK_CHECK_STATUSES",
    "RISK_MSG_ACCOUNT_DRAWDOWN",
    "RISK_MSG_ACCOUNT_AVAILABLE_BALANCE",
    "RISK_MSG_ACCOUNT_NOTIONAL_LIMIT",
    "RISK_MSG_ACCOUNT_MARGIN_RATIO_LIMIT",
    "RISK_MSG_SYMBOL_EXPOSURE_RATIO",
    "RISK_MSG_LONG_LEG_POSITION_LIMIT",
    "RISK_MSG_SHORT_LEG_POSITION_LIMIT",
    "build_risk_checks",
    "build_risk_decision_result",
]
