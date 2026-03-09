import json
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _validate(schema: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    def _type_ok(type_node: Any, value: Any) -> bool:
        if isinstance(type_node, list):
            return any(_type_ok(t, value) for t in type_node)
        if type_node == "object":
            return isinstance(value, dict)
        if type_node == "string":
            return isinstance(value, str)
        if type_node == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if type_node == "null":
            return value is None
        return True

    def check(node: Dict[str, Any], value: Any) -> bool:
        node_type = node.get("type")
        if node_type is not None and not _type_ok(node_type, value):
            return False
        if "const" in node and value != node["const"]:
            return False
        if "enum" in node and value not in node["enum"]:
            return False
        if isinstance(value, str):
            min_len = node.get("minLength")
            if isinstance(min_len, int) and len(value) < min_len:
                return False
        if isinstance(value, int):
            minimum = node.get("minimum")
            if isinstance(minimum, int) and value < minimum:
                return False
        if isinstance(value, dict):
            required = list(node.get("required") or [])
            for k in required:
                if k not in value:
                    return False
            props = dict(node.get("properties") or {})
            for k, v in value.items():
                if k in props and not check(dict(props[k] or {}), v):
                    return False
        return True

    return check(schema, payload)


def test_decision_state_schema_samples() -> None:
    schema_path = Path(PROJECT_ROOT) / "execution_service" / "docs" / "decision_state.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    good = {
        "decision_id": "dec-001",
        "status": "submitted",
        "last_transition": "submitted",
        "execution_action": "add",
        "reject_reason": None,
        "attempts": 2,
        "submitted_at_ms": 1760000000000,
        "last_error": "",
        "source": "execution_service",
        "trace_id": "trace-001",
        "updated_at_ms": 1760000000001,
    }
    assert _validate(schema, good)

    bad = {
        "decision_id": "dec-002",
        "status": "submitted",
        "last_transition": "submitted",
        "attempts": 1,
        "source": "unknown",
        "updated_at_ms": 1760000000001,
    }
    assert not _validate(schema, bad)
