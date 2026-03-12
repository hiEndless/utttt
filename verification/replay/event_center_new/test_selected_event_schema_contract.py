from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.event_center_new.ec.pipeline.replay_cli import validate_selected_contract


def _load_schema() -> dict:
    path = Path(PROJECT_ROOT) / "services" / "event_center_new" / "docs" / "selected_event.schema.json"
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
        "trace",
        "route",
    }
    assert set(props.keys()) == set(required) | {"trigger_event", "source", "trace"}


def test_selected_event_schema_core_enums() -> None:
    schema = _load_schema()
    props = schema.get("properties") or {}
    assert props.get("direction_hint", {}).get("enum") == ["bullish", "bearish", "neutral", "mixed"]
    assert props.get("priority", {}).get("enum") == ["low", "medium", "high"]


def test_selected_event_schema_optional_source_trace_shape() -> None:
    schema = _load_schema()
    props = schema.get("properties") or {}
    source = props.get("source") or {}
    trace = props.get("trace") or {}
    assert set((source.get("properties") or {}).keys()) == {"name", "category"}
    assert trace.get("required") == ["schema_version"]
    assert (trace.get("properties") or {}).get("schema_version", {}).get("minLength") == 1


def test_validate_selected_contract_reports_missing_required_fields() -> None:
    # 中文注释：行为断言，确保契约检查在缺必填字段时会返回结构化错误。
    items = [
        {
            "asset": "ETHUSDT",
            "ts_ms": 1,
            "selected_type": "event.selected",
            "direction_hint": "bullish",
            "priority": "high",
            "context_snapshot": {},
            # 故意缺少 route / trace
        }
    ]
    report = validate_selected_contract(items)
    assert report["ok"] is False
    assert any(
        e.get("error") == "missing_required_fields" and "route" in (e.get("fields") or []) and "trace" in (e.get("fields") or [])
        for e in report["errors"]
    )


def test_validate_selected_contract_reports_missing_trace_schema_version() -> None:
    items = [
        {
            "asset": "ETHUSDT",
            "ts_ms": 1,
            "selected_type": "event.selected",
            "direction_hint": "bullish",
            "priority": "high",
            "context_snapshot": {},
            "trace": {},
            "route": {},
        }
    ]
    report = validate_selected_contract(items)
    assert report["ok"] is False
    assert any(e.get("error") == "missing_trace_schema_version" for e in report["errors"])
