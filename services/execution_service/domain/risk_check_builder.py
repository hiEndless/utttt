from __future__ import annotations

from typing import Any, Dict

from execution_service.domain.risk_check_codes import (
    RISK_CHECK_ACCOUNT_AVAILABLE_BALANCE,
    RISK_CHECK_ACCOUNT_CONSECUTIVE_LOSS_LIMIT,
    RISK_CHECK_ACCOUNT_DAILY_LOSS_LIMIT,
    RISK_CHECK_ACCOUNT_DRAWDOWN_LIMIT,
    RISK_CHECK_ACCOUNT_MARGIN_RATIO_LIMIT,
    RISK_CHECK_ACCOUNT_NOTIONAL_LIMIT,
    RISK_CHECK_LONG_LEG_POSITION_LIMIT,
    RISK_CHECK_SHORT_LEG_POSITION_LIMIT,
    RISK_CHECK_SYMBOL_EXPOSURE_RATIO,
)
from execution_service.domain.risk_check_messages import (
    RISK_MSG_ACCOUNT_AVAILABLE_BALANCE,
    RISK_MSG_ACCOUNT_CONSECUTIVE_LOSS_LIMIT,
    RISK_MSG_ACCOUNT_DAILY_LOSS_LIMIT,
    RISK_MSG_ACCOUNT_DRAWDOWN,
    RISK_MSG_ACCOUNT_MARGIN_RATIO_LIMIT,
    RISK_MSG_ACCOUNT_NOTIONAL_LIMIT,
    RISK_MSG_LONG_LEG_POSITION_LIMIT,
    RISK_MSG_SHORT_LEG_POSITION_LIMIT,
    RISK_MSG_SYMBOL_EXPOSURE_RATIO,
)
from execution_service.domain.risk_check_meta import (
    RISK_CHECK_SCOPE_ACCOUNT,
    RISK_CHECK_SCOPE_POSITION,
    RISK_CHECK_SCOPE_SYMBOL,
    RISK_CHECK_STATUS_FAIL,
    RISK_CHECK_STATUS_PASS,
)


def build_risk_checks(
    *,
    direction: str,
    long_position_size: float,
    short_position_size: float,
    max_long_position_size: float,
    max_short_position_size: float,
    current_drawdown_ratio: float,
    max_drawdown_ratio: float,
    available_balance: float,
    min_available_balance: float,
    account_notional: float,
    max_account_notional: float,
    margin_ratio: float,
    max_margin_ratio: float,
    daily_loss: float,
    max_daily_loss: float,
    consecutive_loss_count: float,
    max_consecutive_loss_count: float,
    symbol_exposure_ratio: float,
    max_symbol_exposure_ratio: float,
) -> list[Dict[str, Any]]:
    checks: list[Dict[str, Any]] = [
        {
            "check": RISK_CHECK_ACCOUNT_DRAWDOWN_LIMIT,
            "scope": RISK_CHECK_SCOPE_ACCOUNT,
            "status": _status(current_drawdown_ratio < max_drawdown_ratio),
            "value": current_drawdown_ratio,
            "threshold": max_drawdown_ratio,
            "message_zh": RISK_MSG_ACCOUNT_DRAWDOWN.format(
                value=current_drawdown_ratio,
                threshold=max_drawdown_ratio,
            ),
        },
        {
            "check": RISK_CHECK_ACCOUNT_AVAILABLE_BALANCE,
            "scope": RISK_CHECK_SCOPE_ACCOUNT,
            "status": _status(available_balance >= min_available_balance),
            "value": available_balance,
            "threshold": min_available_balance,
            "message_zh": RISK_MSG_ACCOUNT_AVAILABLE_BALANCE.format(
                value=available_balance,
                threshold=min_available_balance,
            ),
        },
        {
            "check": RISK_CHECK_SYMBOL_EXPOSURE_RATIO,
            "scope": RISK_CHECK_SCOPE_SYMBOL,
            "status": _status(symbol_exposure_ratio <= max_symbol_exposure_ratio),
            "value": symbol_exposure_ratio,
            "threshold": max_symbol_exposure_ratio,
            "message_zh": RISK_MSG_SYMBOL_EXPOSURE_RATIO.format(
                value=symbol_exposure_ratio,
                threshold=max_symbol_exposure_ratio,
            ),
        },
        {
            "check": RISK_CHECK_ACCOUNT_NOTIONAL_LIMIT,
            "scope": RISK_CHECK_SCOPE_ACCOUNT,
            "status": _status(account_notional <= max_account_notional),
            "value": account_notional,
            "threshold": max_account_notional,
            "message_zh": RISK_MSG_ACCOUNT_NOTIONAL_LIMIT.format(
                value=account_notional,
                threshold=max_account_notional,
            ),
        },
        {
            "check": RISK_CHECK_ACCOUNT_MARGIN_RATIO_LIMIT,
            "scope": RISK_CHECK_SCOPE_ACCOUNT,
            "status": _status(margin_ratio <= max_margin_ratio),
            "value": margin_ratio,
            "threshold": max_margin_ratio,
            "message_zh": RISK_MSG_ACCOUNT_MARGIN_RATIO_LIMIT.format(
                value=margin_ratio,
                threshold=max_margin_ratio,
            ),
        },
        {
            "check": RISK_CHECK_ACCOUNT_DAILY_LOSS_LIMIT,
            "scope": RISK_CHECK_SCOPE_ACCOUNT,
            "status": _status(daily_loss <= max_daily_loss),
            "value": daily_loss,
            "threshold": max_daily_loss,
            "message_zh": RISK_MSG_ACCOUNT_DAILY_LOSS_LIMIT.format(
                value=daily_loss,
                threshold=max_daily_loss,
            ),
        },
        {
            "check": RISK_CHECK_ACCOUNT_CONSECUTIVE_LOSS_LIMIT,
            "scope": RISK_CHECK_SCOPE_ACCOUNT,
            "status": _status(consecutive_loss_count <= max_consecutive_loss_count),
            "value": consecutive_loss_count,
            "threshold": max_consecutive_loss_count,
            "message_zh": RISK_MSG_ACCOUNT_CONSECUTIVE_LOSS_LIMIT.format(
                value=consecutive_loss_count,
                threshold=max_consecutive_loss_count,
            ),
        },
    ]
    if direction == "long":
        checks.append(
            {
                "check": RISK_CHECK_LONG_LEG_POSITION_LIMIT,
                "scope": RISK_CHECK_SCOPE_POSITION,
                "status": _status(long_position_size < max_long_position_size),
                "value": long_position_size,
                "threshold": max_long_position_size,
                "message_zh": RISK_MSG_LONG_LEG_POSITION_LIMIT.format(
                    value=long_position_size,
                    threshold=max_long_position_size,
                ),
            }
        )
    if direction == "short":
        checks.append(
            {
                "check": RISK_CHECK_SHORT_LEG_POSITION_LIMIT,
                "scope": RISK_CHECK_SCOPE_POSITION,
                "status": _status(short_position_size < max_short_position_size),
                "value": short_position_size,
                "threshold": max_short_position_size,
                "message_zh": RISK_MSG_SHORT_LEG_POSITION_LIMIT.format(
                    value=short_position_size,
                    threshold=max_short_position_size,
                ),
            }
        )
    return checks


def _status(passed: bool) -> str:
    return RISK_CHECK_STATUS_PASS if passed else RISK_CHECK_STATUS_FAIL
