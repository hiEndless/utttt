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
        "order_result": {"retry_meta": {"attempts": 1, "max_retries": 0, "status": "failed"}}
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
