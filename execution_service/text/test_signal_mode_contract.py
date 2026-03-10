import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_schema(path: str) -> dict:
    schema_path = Path(PROJECT_ROOT) / path
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_signal_result_uses_mode_ref() -> None:
    signal_schema = _load_schema("execution_service/docs/execution_signal_result.schema.json")
    assert signal_schema.get("properties", {}).get("mode", {}).get("$ref", "") == "./signal_mode.schema.json#/properties/mode"


def test_signal_mode_enum_frozen() -> None:
    mode_schema = _load_schema("execution_service/docs/signal_mode.schema.json")
    enum_values = mode_schema.get("properties", {}).get("mode", {}).get("enum", [])
    assert enum_values == ["simulated"]

