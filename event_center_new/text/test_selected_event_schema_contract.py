from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_schema() -> dict:
    path = Path(PROJECT_ROOT) / "event_center_new" / "docs" / "selected_event.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_selected_event_schema_required_and_allowed_fields() -> None:
    schema = _load_schema()
    required = schema.get("required") or []
    props = schema.get("properties") or {}
    assert schema.get("type") == "object"
    assert schema.get("additionalProperties") is False
    assert set(required) == {
        "asset",
        "ts_ms",
        "selected_type",
        "direction_hint",
        "priority",
        "context_snapshot",
        "route",
    }
    assert set(props.keys()) == set(required) | {"trigger_event"}


def test_selected_event_schema_core_enums() -> None:
    schema = _load_schema()
    props = schema.get("properties") or {}
    assert props.get("direction_hint", {}).get("enum") == ["bullish", "bearish", "neutral", "mixed"]
    assert props.get("priority", {}).get("enum") == ["low", "medium", "high"]
