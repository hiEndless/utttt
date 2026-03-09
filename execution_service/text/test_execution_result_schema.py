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
        if type_node == "array":
            return isinstance(value, list)
        if type_node == "null":
            return value is None
        return True

    def check(node: Dict[str, Any], value: Any) -> bool:
        node_type = node.get("type")
        if node_type is not None and not _type_ok(node_type, value):
            return False
        if "enum" in node and value not in node["enum"]:
            return False
        if isinstance(value, str):
            min_len = node.get("minLength")
            if isinstance(min_len, int) and len(value) < min_len:
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
        if isinstance(value, list):
            item_schema = node.get("items")
            if isinstance(item_schema, dict):
                for item in value:
                    if not check(dict(item_schema), item):
                        return False
        return True

    return check(schema, payload)


def test_execution_result_schema_samples() -> None:
    schema_path = Path(PROJECT_ROOT) / "execution_service" / "docs" / "execution_result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    good = {
        "decision_id": "dec-001",
        "execution_action": "hold",
        "reject_reason": "position_limit_reached",
        "applied_risk_rules": ["max_position_limit"],
        "notes": "当前仓位已达上限"
    }
    assert _validate(schema, good)

    good_submit_fail = {
        "decision_id": "dec-002",
        "execution_action": "skip",
        "reject_reason": "execution_submit_failed",
        "applied_risk_rules": ["execution_submit_fallback"],
        "order_result": {"retry_meta": {"status": "failed"}}
    }
    assert _validate(schema, good_submit_fail)

    bad = {
        "decision_id": "dec-003",
        "execution_action": "open",
        "reject_reason": "position_limit_reached",
        "applied_risk_rules": []
    }
    assert not _validate(schema, bad)
