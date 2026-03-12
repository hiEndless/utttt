from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

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


def test_risk_check_message_templates_render_stable_format() -> None:
    render = [
        RISK_MSG_ACCOUNT_DRAWDOWN.format(value=0.01, threshold=0.2),
        RISK_MSG_ACCOUNT_AVAILABLE_BALANCE.format(value=10, threshold=100),
        RISK_MSG_ACCOUNT_NOTIONAL_LIMIT.format(value=2000, threshold=1000),
        RISK_MSG_ACCOUNT_MARGIN_RATIO_LIMIT.format(value=0.6, threshold=0.5),
        RISK_MSG_ACCOUNT_DAILY_LOSS_LIMIT.format(value=300, threshold=200),
        RISK_MSG_ACCOUNT_CONSECUTIVE_LOSS_LIMIT.format(value=5, threshold=3),
        RISK_MSG_SYMBOL_EXPOSURE_RATIO.format(value=0.12, threshold=0.5),
        RISK_MSG_LONG_LEG_POSITION_LIMIT.format(value=0.3, threshold=1),
        RISK_MSG_SHORT_LEG_POSITION_LIMIT.format(value=0.4, threshold=1),
    ]
    for msg in render:
        assert "当前=" in msg
        assert "阈值=" in msg
        assert "," in msg
