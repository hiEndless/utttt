from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

_SCHEMA_CACHE: Dict[str, Any] | None = None


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "docs" / "llm_signal_decision.schema.json"


def _load_schema() -> Dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        _SCHEMA_CACHE = json.loads(_schema_path().read_text(encoding="utf-8"))
    return dict(_SCHEMA_CACHE or {})


def _validate_node(node: Dict[str, Any], value: Any, path: str = "$") -> List[str]:
    errors: List[str] = []
    node_type = node.get("type")
    if node_type == "object" and not isinstance(value, dict):
        return [f"{path}: expected object"]
    if node_type == "string" and not isinstance(value, str):
        return [f"{path}: expected string"]
    if node_type == "number" and not isinstance(value, (int, float)):
        return [f"{path}: expected number"]
    if node_type == "array" and not isinstance(value, list):
        return [f"{path}: expected array"]

    if "enum" in node and value not in node["enum"]:
        errors.append(f"{path}: value not in enum")
    if "minimum" in node:
        try:
            if float(value) < float(node["minimum"]):
                errors.append(f"{path}: value below minimum")
        except Exception:
            errors.append(f"{path}: minimum validation failed")
    if "maximum" in node:
        try:
            if float(value) > float(node["maximum"]):
                errors.append(f"{path}: value above maximum")
        except Exception:
            errors.append(f"{path}: maximum validation failed")

    if isinstance(value, dict):
        required = list(node.get("required") or [])
        props = dict(node.get("properties") or {})
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required key '{key}'")
        for key, child in value.items():
            if key in props:
                errors.extend(_validate_node(dict(props[key] or {}), child, f"{path}.{key}"))
            elif node.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected key '{key}'")

    if isinstance(value, list):
        item_schema = dict(node.get("items") or {})
        if item_schema:
            for idx, item in enumerate(value):
                errors.extend(_validate_node(item_schema, item, f"{path}[{idx}]"))
    return errors


def validate_llm_signal_decision_payload(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    schema = _load_schema()
    errors = _validate_node(schema, dict(payload or {}))
    return (len(errors) == 0), errors
