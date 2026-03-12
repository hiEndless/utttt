from pathlib import Path
import sys
import json

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from execution_service.domain.risk_check_builder import build_risk_checks
from verification.validators.execution_service.schema_utils import validate_payload_with_local_refs


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
        account_notional=200.0,
        max_account_notional=1000.0,
        margin_ratio=0.2,
        max_margin_ratio=0.8,
        daily_loss=10.0,
        max_daily_loss=100.0,
        consecutive_loss_count=1.0,
        max_consecutive_loss_count=3.0,
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
        account_notional=2000.0,
        max_account_notional=1000.0,
        margin_ratio=0.9,
        max_margin_ratio=0.8,
        daily_loss=200.0,
        max_daily_loss=100.0,
        consecutive_loss_count=5.0,
        max_consecutive_loss_count=3.0,
        symbol_exposure_ratio=0.6,
        max_symbol_exposure_ratio=0.5,
    )
    drawdown = next(c for c in checks if c["check"] == "account_drawdown_limit")
    short_leg = next(c for c in checks if c["check"] == "short_leg_position_limit")
    account_notional = next(c for c in checks if c["check"] == "account_notional_limit")
    margin_ratio = next(c for c in checks if c["check"] == "account_margin_ratio_limit")
    daily_loss = next(c for c in checks if c["check"] == "account_daily_loss_limit")
    consecutive_loss = next(c for c in checks if c["check"] == "account_consecutive_loss_limit")
    assert drawdown["status"] == "fail"
    assert short_leg["status"] == "fail"
    assert account_notional["status"] == "fail"
    assert margin_ratio["status"] == "fail"
    assert daily_loss["status"] == "fail"
    assert consecutive_loss["status"] == "fail"


def test_build_risk_checks_items_match_signal_result_schema() -> None:
    schema_path = ROOT_DIR / "execution_service" / "docs" / "risk_checks.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    item_schema = (
        schema.get("properties", {})
        .get("risk_checks", {})
        .get("items", {})
    )
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
        account_notional=200.0,
        max_account_notional=1000.0,
        margin_ratio=0.2,
        max_margin_ratio=0.8,
        daily_loss=10.0,
        max_daily_loss=100.0,
        consecutive_loss_count=1.0,
        max_consecutive_loss_count=3.0,
        symbol_exposure_ratio=0.2,
        max_symbol_exposure_ratio=0.5,
    )
    base_dir = ROOT_DIR / "execution_service" / "docs"
    for item in checks:
        assert validate_payload_with_local_refs(item_schema, item, base_dir)
