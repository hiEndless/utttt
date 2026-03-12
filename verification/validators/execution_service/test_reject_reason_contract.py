import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_schema(path: str) -> dict:
    schema_path = Path(PROJECT_ROOT) / path
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_execution_result_and_decision_state_use_reject_reason_ref() -> None:
    execution_result_schema = _load_schema("services/execution_service/docs/execution_result.schema.json")
    decision_state_schema = _load_schema("services/execution_service/docs/decision_state.schema.json")
    expected_ref = "./reject_reason.schema.json#/properties/reject_reason"
    assert execution_result_schema.get("properties", {}).get("reject_reason", {}).get("$ref", "") == expected_ref
    assert decision_state_schema.get("properties", {}).get("reject_reason", {}).get("$ref", "") == expected_ref


def test_reject_reason_enum_frozen() -> None:
    reject_reason_schema = _load_schema("services/execution_service/docs/reject_reason.schema.json")
    expected = [
        None,
        "position_limit_reached",
        "cooldown_active",
        "max_drawdown_exceeded",
        "account_notional_exceeded",
        "account_margin_ratio_exceeded",
        "daily_loss_exceeded",
        "consecutive_loss_exceeded",
        "direction_conflict_with_position",
        "execution_submit_failed",
        "idempotency_in_progress",
    ]
    assert reject_reason_schema.get("properties", {}).get("reject_reason", {}).get("enum", []) == expected
