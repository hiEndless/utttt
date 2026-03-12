import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_schema(path: str) -> dict:
    schema_path = Path(PROJECT_ROOT) / path
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_decision_state_uses_status_refs() -> None:
    decision_state_schema = _load_schema("services/execution_service/docs/decision_state.schema.json")
    assert (
        decision_state_schema.get("properties", {}).get("status", {}).get("$ref", "")
        == "./decision_state_status.schema.json#/properties/status"
    )
    assert (
        decision_state_schema.get("properties", {}).get("last_transition", {}).get("$ref", "")
        == "./decision_state_status.schema.json#/properties/last_transition"
    )


def test_decision_state_status_enum_frozen() -> None:
    status_schema = _load_schema("services/execution_service/docs/decision_state_status.schema.json")
    expected = ["pending", "submitted", "failed", "skipped", "decided", "filled", "canceled", "rejected"]
    assert status_schema.get("properties", {}).get("status", {}).get("enum", []) == expected
    assert status_schema.get("properties", {}).get("last_transition", {}).get("enum", []) == expected

