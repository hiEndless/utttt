import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from execution_service.text.schema_utils import validate_payload_with_local_refs


def test_decision_state_schema_samples() -> None:
    schema_path = Path(PROJECT_ROOT) / "execution_service" / "docs" / "decision_state.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    good = {
        "decision_id": "dec-001",
        "account_id": "main",
        "status": "submitted",
        "last_transition": "submitted",
        "execution_action": "add",
        "reject_reason": None,
        "risk_state": "normal",
        "attempts": 2,
        "submitted_at_ms": 1760000000000,
        "last_error": "",
        "rule_debug": {
            "hit_rule": "passed_all_rules",
            "rule_priority_order": ["position_limit", "cooldown"],
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
                    "value": 0.1,
                    "threshold": 1.0,
                    "note_zh": "仓位上限检查(多头): 当前=0.1000, 阈值=1.0000",
                }
            ],
        },
        "source": "execution_service",
        "trace_id": "trace-001",
        "updated_at_ms": 1760000000001,
    }
    assert validate_payload_with_local_refs(
        schema, good, Path(PROJECT_ROOT) / "execution_service" / "docs"
    )

    good_reconciled = {
        "decision_id": "dec-001",
        "account_id": "main",
        "status": "filled",
        "last_transition": "filled",
        "attempts": 1,
        "source": "execution_service",
        "updated_at_ms": 1760000000002,
    }
    assert validate_payload_with_local_refs(
        schema, good_reconciled, Path(PROJECT_ROOT) / "execution_service" / "docs"
    )

    bad = {
        "decision_id": "dec-002",
        "account_id": "main",
        "status": "submitted",
        "last_transition": "submitted",
        "attempts": 1,
        "source": "unknown",
        "updated_at_ms": 1760000000001,
    }
    assert not validate_payload_with_local_refs(
        schema, bad, Path(PROJECT_ROOT) / "execution_service" / "docs"
    )
