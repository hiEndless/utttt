import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_schema(path: str) -> dict:
    schema_path = Path(PROJECT_ROOT) / path
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_rule_debug_uses_evaluation_trace_ref() -> None:
    rule_debug_schema = _load_schema("services/execution_service/docs/rule_debug.schema.json")
    eval_trace_schema = _load_schema("services/execution_service/docs/evaluation_trace.schema.json")
    trace_ref = rule_debug_schema.get("properties", {}).get("evaluation_trace", {}).get("$ref", "")
    assert trace_ref == "./evaluation_trace.schema.json#/properties/evaluation_trace"
    required_fields = (
        eval_trace_schema.get("properties", {})
        .get("evaluation_trace", {})
        .get("items", {})
        .get("required", [])
    )
    assert required_fields == ["order", "rule", "scope", "status", "value", "threshold", "note_zh"]

