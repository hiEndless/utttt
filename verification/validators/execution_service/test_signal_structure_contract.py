import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_schema(path: str) -> dict:
    schema_path = Path(PROJECT_ROOT) / path
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_signal_result_uses_scope_and_position_refs() -> None:
    signal_schema = _load_schema("services/execution_service/docs/execution_signal_result.schema.json")
    assert signal_schema.get("properties", {}).get("scope", {}).get("$ref", "") == "./signal_scope.schema.json#/properties/scope"
    assert (
        signal_schema.get("properties", {}).get("position_before", {}).get("$ref", "")
        == "./position_before.schema.json#/properties/position_before"
    )
    assert (
        signal_schema.get("properties", {}).get("position_after_simulation", {}).get("$ref", "")
        == "./position_after_simulation.schema.json#/properties/position_after_simulation"
    )


def test_scope_and_position_required_fields_frozen() -> None:
    scope_schema = _load_schema("services/execution_service/docs/signal_scope.schema.json")
    before_schema = _load_schema("services/execution_service/docs/position_before.schema.json")
    after_schema = _load_schema("services/execution_service/docs/position_after_simulation.schema.json")
    assert scope_schema.get("properties", {}).get("scope", {}).get("required", []) == ["exchange", "account_id", "symbol"]
    assert before_schema.get("properties", {}).get("position_before", {}).get("required", []) == [
        "mode",
        "long_position_size",
        "short_position_size",
        "net_position_size",
    ]
    assert after_schema.get("properties", {}).get("position_after_simulation", {}).get("required", []) == [
        "long_position_size",
        "short_position_size",
        "net_position_size",
    ]

