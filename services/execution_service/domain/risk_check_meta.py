from __future__ import annotations

# 中文注释：signal_result.risk_checks 维度枚举单点定义，避免代码与 schema 漂移。
RISK_CHECK_SCOPE_ACCOUNT = "account"
RISK_CHECK_SCOPE_SYMBOL = "symbol"
RISK_CHECK_SCOPE_POSITION = "position"

RISK_CHECK_STATUS_PASS = "pass"
RISK_CHECK_STATUS_FAIL = "fail"

RISK_CHECK_SCOPES = (
    RISK_CHECK_SCOPE_ACCOUNT,
    RISK_CHECK_SCOPE_SYMBOL,
    RISK_CHECK_SCOPE_POSITION,
)

RISK_CHECK_STATUSES = (
    RISK_CHECK_STATUS_PASS,
    RISK_CHECK_STATUS_FAIL,
)
