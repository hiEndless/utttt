from __future__ import annotations

HORIZON_POLICY_REASON_WAIT_CONFIRMATION = "horizon_policy_wait_confirmation"
HORIZON_POLICY_REASON_REDUCE_RISK = "horizon_policy_reduce_risk"
HORIZON_POLICY_REASON_BLOCKED_GENERIC = "horizon_policy_blocked"
HORIZON_POLICY_REASON_POLICY_REASON_PREFIX = "policy_reason:"

HORIZON_POLICY_REASON_CODES = (
    HORIZON_POLICY_REASON_WAIT_CONFIRMATION,
    HORIZON_POLICY_REASON_REDUCE_RISK,
    HORIZON_POLICY_REASON_BLOCKED_GENERIC,
)


def horizon_policy_reason_code(suggested_policy: str) -> str:
    v = str(suggested_policy or "").strip().lower()
    if v == "wait_confirmation":
        return HORIZON_POLICY_REASON_WAIT_CONFIRMATION
    if v == "reduce_risk":
        return HORIZON_POLICY_REASON_REDUCE_RISK
    return HORIZON_POLICY_REASON_BLOCKED_GENERIC


def horizon_policy_reason_tag(policy_reason: str) -> str:
    reason = str(policy_reason or "unknown_reason").strip() or "unknown_reason"
    return f"{HORIZON_POLICY_REASON_POLICY_REASON_PREFIX}{reason}"

