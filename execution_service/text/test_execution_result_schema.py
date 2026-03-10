import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from execution_service.text.schema_utils import validate_payload_with_local_refs


def test_execution_result_schema_samples() -> None:
    schema_path = Path(PROJECT_ROOT) / "execution_service" / "docs" / "execution_result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    good = {
        "decision_id": "dec-001",
        "execution_action": "hold",
        "reject_reason": "position_limit_reached",
        "applied_risk_rules": ["max_position_limit"],
        "notes": "当前仓位已达上限"
    }
    assert validate_payload_with_local_refs(
        schema, good, Path(PROJECT_ROOT) / "execution_service" / "docs"
    )

    good_submit_fail = {
        "decision_id": "dec-002",
        "execution_action": "skip",
        "reject_reason": "execution_submit_failed",
        "applied_risk_rules": ["execution_submit_fallback"],
        "order_result": {"retry_meta": {"attempts": 1, "max_retries": 0, "status": "failed"}},
        "signal_result": {
            "signal_action": "skip",
            "risk_state": "reduce_only",
            "mode": "simulated",
            "scope": {"exchange": "binance", "account_id": "main", "symbol": "ETHUSDT"},
            "position_before": {
                "mode": "one_way",
                "long_position_size": 0.0,
                "short_position_size": 0.0,
                "net_position_size": 0.0,
            },
            "position_after_simulation": {
                "long_position_size": 0.0,
                "short_position_size": 0.0,
                "net_position_size": 0.0,
            },
            "risk_checks": [
                {
                    "check": "account_drawdown_limit",
                    "scope": "account",
                    "status": "pass",
                    "value": 0.01,
                    "threshold": 0.2,
                    "message_zh": "账户回撤检查: 当前=0.0100, 阈值=0.2000",
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
                "current_risk_state": "reduce_only",
                "matched_at_ms": 1760000000001,
                "evaluation_trace": [
                    {
                        "order": 1,
                        "rule": "position_limit",
                        "scope": "position",
                        "status": "pass",
                        "value": 0.1,
                        "threshold": 1.0,
                        "note_zh": "仓位上限检查(多头): 当前=0.1000, 阈值=1.0000",
                    }
                ],
            },
        },
    }
    assert validate_payload_with_local_refs(
        schema, good_submit_fail, Path(PROJECT_ROOT) / "execution_service" / "docs"
    )

    bad = {
        "decision_id": "dec-003",
        "execution_action": "open",
        "reject_reason": "position_limit_reached",
        "applied_risk_rules": []
    }
    assert not validate_payload_with_local_refs(
        schema, bad, Path(PROJECT_ROOT) / "execution_service" / "docs"
    )
