from __future__ import annotations

# 中文注释：signal_result.risk_checks.check 单点定义，避免代码与 schema 枚举漂移。
RISK_CHECK_ACCOUNT_DRAWDOWN_LIMIT = "account_drawdown_limit"
RISK_CHECK_ACCOUNT_AVAILABLE_BALANCE = "account_available_balance"
RISK_CHECK_SYMBOL_EXPOSURE_RATIO = "symbol_exposure_ratio"
RISK_CHECK_LONG_LEG_POSITION_LIMIT = "long_leg_position_limit"
RISK_CHECK_SHORT_LEG_POSITION_LIMIT = "short_leg_position_limit"

RISK_CHECK_CODES = (
    RISK_CHECK_ACCOUNT_DRAWDOWN_LIMIT,
    RISK_CHECK_ACCOUNT_AVAILABLE_BALANCE,
    RISK_CHECK_SYMBOL_EXPOSURE_RATIO,
    RISK_CHECK_LONG_LEG_POSITION_LIMIT,
    RISK_CHECK_SHORT_LEG_POSITION_LIMIT,
)
