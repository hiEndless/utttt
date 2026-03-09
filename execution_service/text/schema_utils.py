import json
from pathlib import Path
from typing import Any, Dict


def validate_payload_with_local_refs(schema: Dict[str, Any], payload: Dict[str, Any], base_dir: Path) -> bool:
    """最小 JSON Schema 校验器：支持类型/枚举/边界/required/items/const 与同目录本地 $ref。"""

    def _resolve_ref(node: Dict[str, Any]) -> Dict[str, Any]:
        ref = node.get("$ref")
        if not isinstance(ref, str):
            return node
        ref_path = (base_dir / ref).resolve()
        return json.loads(ref_path.read_text(encoding="utf-8"))

    def _type_ok(type_node: Any, value: Any) -> bool:
        if isinstance(type_node, list):
            return any(_type_ok(t, value) for t in type_node)
        if type_node == "object":
            return isinstance(value, dict)
        if type_node == "string":
            return isinstance(value, str)
        if type_node == "array":
            return isinstance(value, list)
        if type_node == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if type_node == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if type_node == "boolean":
            return isinstance(value, bool)
        if type_node == "null":
            return value is None
        return True

    def _check(node: Dict[str, Any], value: Any) -> bool:
        node = _resolve_ref(node)
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

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            minimum = node.get("minimum")
            maximum = node.get("maximum")
            if isinstance(minimum, (int, float)) and value < minimum:
                return False
            if isinstance(maximum, (int, float)) and value > maximum:
                return False

        if isinstance(value, dict):
            required = list(node.get("required") or [])
            for key in required:
                if key not in value:
                    return False
            props = dict(node.get("properties") or {})
            for key, item in value.items():
                if key in props and not _check(dict(props[key] or {}), item):
                    return False

        if isinstance(value, list):
            item_schema = node.get("items")
            if isinstance(item_schema, dict):
                for item in value:
                    if not _check(dict(item_schema or {}), item):
                        return False

        return True

    return _check(schema, payload)
