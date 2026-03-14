import json
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _validate(schema: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    """最小 JSON Schema 验证器（覆盖本项目当前 schema 用到的语法）。"""

    def check(node: Dict[str, Any], value: Any) -> bool:
        node_type = node.get("type")
        if node_type == "object" and not isinstance(value, dict):
            return False
        if node_type == "string" and not isinstance(value, str):
            return False
        if "const" in node and value != node["const"]:
            return False
        if "enum" in node and value not in node["enum"]:
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

        one_of = node.get("oneOf")
        if isinstance(one_of, list):
            matches = 0
            for candidate in one_of:
                if check(dict(candidate or {}), value):
                    matches += 1
            return matches == 1
        return True

    return check(schema, payload)


def test_runner_output_schema_samples() -> None:
    schema_path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "docs" / "runner_output.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    samples = [
        {"source": "execution", "action": "reduce", "reason": "position_limit_reached", "notes": "x"},
        {"source": "agent_fallback", "action": "add", "direction": "long", "notes": "x"},
        {"source": "agent", "action": "hold", "direction": "neutral", "notes": "x"},
    ]
    for payload in samples:
        assert _validate(schema, payload)

    bad = {"source": "execution", "action": "reduce", "notes": "x"}
    assert not _validate(schema, bad)
