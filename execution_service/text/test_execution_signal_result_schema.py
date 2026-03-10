import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from execution_service.text.schema_utils import validate_payload_with_local_refs


def test_execution_signal_result_schema_samples() -> None:
    schema_path = Path(PROJECT_ROOT) / "execution_service" / "docs" / "execution_signal_result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    base_dir = Path(PROJECT_ROOT) / "execution_service" / "docs"

    good = {
        "signal_action": "add_long",
        "risk_state": "normal",
        "mode": "simulated",
        "scope": {"exchange": "binance", "account_id": "main", "symbol": "ETHUSDT"},
        "position_before": {
            "mode": "hedge",
            "long_position_size": 0.5,
            "short_position_size": 0.2,
            "net_position_size": 0.3,
        },
        "position_after_simulation": {
            "long_position_size": 0.6,
            "short_position_size": 0.2,
            "net_position_size": 0.4,
        },
        "risk_checks": [
            {
                "check": "account_drawdown_limit",
                "scope": "account",
                "status": "pass",
                "value": 0.05,
                "threshold": 0.2,
                "message_zh": "账户回撤检查: 当前=0.0500, 阈值=0.2000",
            }
        ],
        "rule_debug": {
            "hit_rule": "passed_all_rules",
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
            "hit_rule_value": None,
            "hit_rule_threshold": None,
            "previous_risk_state": "normal",
            "current_risk_state": "normal",
            "risk_state_changed": False,
            "matched_at_ms": 1760000000000,
            "evaluation_trace": [
                {
                    "order": 1,
                    "rule": "position_limit",
                    "scope": "position",
                    "status": "pass",
                    "value": 0.3,
                    "threshold": 1.0,
                    "note_zh": "仓位上限检查(多头): 当前=0.3000, 阈值=1.0000",
                }
            ],
        },
    }
    assert validate_payload_with_local_refs(schema, good, base_dir)

    bad = {
        "signal_action": "buy",
        "risk_state": "risky",
        "mode": "simulated",
        "scope": {"exchange": "binance", "account_id": "main", "symbol": "ETHUSDT"},
        "position_before": {
            "mode": "hedge",
            "long_position_size": 0.5,
            "short_position_size": 0.2,
            "net_position_size": 0.3,
        },
        "position_after_simulation": {
            "long_position_size": 0.6,
            "short_position_size": 0.2,
            "net_position_size": 0.4,
        },
        "risk_checks": [
            {
                "check": "account_drawdown_limit",
                "scope": "account",
                "status": "pass",
                "value": 0.05,
                "threshold": 0.2
            }
        ],
        "rule_debug": {
            "hit_rule": "",
            "rule_priority_order": [],
            "hit_rule_value": None,
            "hit_rule_threshold": None,
            "previous_risk_state": "unknown",
            "current_risk_state": "unknown",
            "matched_at_ms": 0,
            "evaluation_trace": [
                {"order": 0, "rule": "", "scope": "unknown", "status": "unknown", "value": None, "threshold": None, "note_zh": ""}
            ],
        },
    }
    assert not validate_payload_with_local_refs(schema, bad, base_dir)
