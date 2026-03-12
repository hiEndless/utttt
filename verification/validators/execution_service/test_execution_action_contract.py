import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_schema(path: str) -> dict:
    schema_path = Path(PROJECT_ROOT) / path
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_execution_result_and_decision_state_use_execution_enum_ref() -> None:
    execution_result_schema = _load_schema("services/execution_service/docs/execution_result.schema.json")
    decision_state_schema = _load_schema("services/execution_service/docs/decision_state.schema.json")
    expected_ref = "./execution_enums.schema.json#/properties/execution_action"
    assert (
        execution_result_schema.get("properties", {}).get("execution_action", {}).get("$ref", "")
        == expected_ref
    )
    assert (
        decision_state_schema.get("properties", {}).get("execution_action", {}).get("$ref", "")
        == expected_ref
    )


def test_execution_action_enum_frozen() -> None:
    action_schema = _load_schema("services/execution_service/docs/execution_action.schema.json")
    enums_schema = _load_schema("services/execution_service/docs/execution_enums.schema.json")
    expected = ["add", "reduce", "hold", "exit", "skip"]
    action_node = action_schema.get("properties", {}).get("execution_action", {})
    assert action_node.get("$ref") == "./execution_enums.schema.json#/properties/execution_action"
    assert enums_schema.get("properties", {}).get("execution_action", {}).get("enum", []) == expected
