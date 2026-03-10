import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from execution_service.text.schema_utils import validate_payload_with_local_refs


def test_risk_policy_schema_samples() -> None:
    schema_path = Path(PROJECT_ROOT) / "execution_service" / "docs" / "risk_policy.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    base_dir = Path(PROJECT_ROOT) / "execution_service" / "docs"

    good = {
        "max_position_size": 1.0,
        "max_long_position_size": 1.0,
        "max_short_position_size": 1.0,
        "max_drawdown_ratio": 0.2,
        "position_mode": "hedge",
        "allow_dual_side": True,
        "min_available_balance": 100.0,
        "max_symbol_exposure_ratio": 0.4,
        "max_account_notional": 100000.0,
        "max_margin_ratio": 0.5,
        "max_daily_loss": 2000.0,
        "max_consecutive_loss_count": 3,
        "simulation_step_size": 0.1,
        "rule_priority_order": [
            "position_limit",
            "cooldown",
            "max_drawdown",
            "account_notional",
            "margin_ratio",
            "daily_loss",
            "consecutive_loss",
            "direction_conflict",
        ],
    }
    assert validate_payload_with_local_refs(schema, good, base_dir)

    bad = dict(good)
    bad["max_drawdown_ratio"] = 1.2
    assert not validate_payload_with_local_refs(schema, bad, base_dir)

    bad_order = dict(good)
    bad_order["rule_priority_order"] = [
        "position_limit",
        "cooldown",
        "unknown_rule",
        "account_notional",
        "margin_ratio",
        "daily_loss",
        "consecutive_loss",
        "direction_conflict",
    ]
    assert not validate_payload_with_local_refs(schema, bad_order, base_dir)
