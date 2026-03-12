import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_schema(path: str) -> dict:
    schema_path = Path(PROJECT_ROOT) / path
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_execution_result_and_decision_state_use_policy_snapshot_ref() -> None:
    execution_result_schema = _load_schema("services/execution_service/docs/execution_result.schema.json")
    decision_state_schema = _load_schema("services/execution_service/docs/decision_state.schema.json")
    assert execution_result_schema.get("properties", {}).get("policy_snapshot", {}).get("$ref", "") == "./policy_snapshot.schema.json"
    assert decision_state_schema.get("properties", {}).get("policy_snapshot", {}).get("$ref", "") == "./policy_snapshot.schema.json"


def test_policy_snapshot_schema_frozen() -> None:
    schema = _load_schema("services/execution_service/docs/policy_snapshot.schema.json")
    assert schema.get("required", []) == ["policy_version", "ruleset_hash"]
    assert schema.get("properties", {}).get("policy_version", {}).get("minLength") == 1
    assert schema.get("properties", {}).get("ruleset_hash", {}).get("minLength") == 1
