import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_schema(path: str) -> dict:
    schema_path = Path(PROJECT_ROOT) / path
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_signal_result_uses_signal_action_ref() -> None:
    signal_schema = _load_schema("execution_service/docs/execution_signal_result.schema.json")
    assert (
        signal_schema.get("properties", {}).get("signal_action", {}).get("$ref", "")
        == "./signal_action.schema.json#/properties/signal_action"
    )


def test_signal_action_enum_frozen() -> None:
    action_schema = _load_schema("execution_service/docs/signal_action.schema.json")
    enum_values = action_schema.get("properties", {}).get("signal_action", {}).get("enum", [])
    assert enum_values == [
        "add_long",
        "add_short",
        "reduce_long",
        "reduce_short",
        "hold",
        "skip",
        "exit_all",
    ]

