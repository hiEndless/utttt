from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from execution_service.domain.risk_check_builder import build_risk_checks


def test_build_risk_checks_includes_long_leg_and_message() -> None:
    checks = build_risk_checks(
        direction="long",
        long_position_size=0.3,
        short_position_size=0.1,
        max_long_position_size=1.0,
        max_short_position_size=1.0,
        current_drawdown_ratio=0.01,
        max_drawdown_ratio=0.2,
        available_balance=100.0,
        min_available_balance=50.0,
        symbol_exposure_ratio=0.2,
        max_symbol_exposure_ratio=0.5,
    )
    assert any(c["check"] == "long_leg_position_limit" for c in checks)
    assert all(isinstance(c.get("message_zh"), str) and c["message_zh"] for c in checks)


def test_build_risk_checks_marks_failure_by_threshold() -> None:
    checks = build_risk_checks(
        direction="short",
        long_position_size=0.3,
        short_position_size=1.0,
        max_long_position_size=1.0,
        max_short_position_size=1.0,
        current_drawdown_ratio=0.3,
        max_drawdown_ratio=0.2,
        available_balance=10.0,
        min_available_balance=50.0,
        symbol_exposure_ratio=0.6,
        max_symbol_exposure_ratio=0.5,
    )
    drawdown = next(c for c in checks if c["check"] == "account_drawdown_limit")
    short_leg = next(c for c in checks if c["check"] == "short_leg_position_limit")
    assert drawdown["status"] == "fail"
    assert short_leg["status"] == "fail"

