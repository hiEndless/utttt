import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_schema(path: str) -> dict:
    schema_path = Path(PROJECT_ROOT) / path
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_risk_policy_and_position_before_use_position_mode_ref() -> None:
    risk_policy_schema = _load_schema("execution_service/docs/risk_policy.schema.json")
    position_before_schema = _load_schema("execution_service/docs/position_before.schema.json")
    assert (
        risk_policy_schema.get("properties", {}).get("position_mode", {}).get("$ref", "")
        == "./position_mode.schema.json#/properties/position_mode"
    )
    assert (
        position_before_schema.get("properties", {})
        .get("position_before", {})
        .get("properties", {})
        .get("mode", {})
        .get("$ref", "")
        == "./position_mode.schema.json#/properties/mode"
    )


def test_position_mode_enum_frozen() -> None:
    mode_schema = _load_schema("execution_service/docs/position_mode.schema.json")
    expected = ["one_way", "hedge"]
    assert mode_schema.get("properties", {}).get("mode", {}).get("enum", []) == expected
    assert mode_schema.get("properties", {}).get("position_mode", {}).get("enum", []) == expected

