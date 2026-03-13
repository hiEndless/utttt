import json
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _validate(schema: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    def check(node: Dict[str, Any], value: Any) -> bool:
        node_type = node.get("type")
        if node_type == "object" and not isinstance(value, dict):
            return False
        if node_type == "string" and not isinstance(value, str):
            return False
        if node_type == "number" and not isinstance(value, (int, float)):
            return False
        if node_type == "array" and not isinstance(value, list):
            return False
        if "enum" in node and value not in node["enum"]:
            return False
        if "minimum" in node:
            try:
                if float(value) < float(node["minimum"]):
                    return False
            except Exception:
                return False
        if "maximum" in node:
            try:
                if float(value) > float(node["maximum"]):
                    return False
            except Exception:
                return False

        if isinstance(value, dict):
            required = list(node.get("required") or [])
            for k in required:
                if k not in value:
                    return False
            props = dict(node.get("properties") or {})
            for k, v in value.items():
                if k in props:
                    if not check(dict(props[k] or {}), v):
                        return False
                elif node.get("additionalProperties") is False:
                    return False

        if isinstance(value, list):
            item_schema = dict(node.get("items") or {})
            if item_schema:
                for item in value:
                    if not check(item_schema, item):
                        return False
        return True

    return check(schema, payload)


def test_llm_signal_decision_schema_samples() -> None:
    schema_path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "docs" / "llm_signal_decision.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    good = {
        "signal_verdict": "accept",
        "signal_direction": "long",
        "confidence_score": 0.81,
        "reasons": ["breakout_confirmed"],
    }
    assert _validate(schema, good)

    bad_unknown = {
        "signal_verdict": "accept",
        "signal_direction": "long",
        "confidence_score": 0.81,
        "foo": "bar",
    }
    assert not _validate(schema, bad_unknown)

    bad_score = {
        "signal_verdict": "accept",
        "signal_direction": "long",
        "confidence_score": 1.2,
    }
    assert not _validate(schema, bad_score)
