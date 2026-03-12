from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.event_center_new.runtime.replay_main import _to_summary_report


def _load_schema() -> dict:
    path = Path(PROJECT_ROOT) / "services" / "event_center_new" / "docs" / "replay_summary.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_replay_summary_schema_surface() -> None:
    schema = _load_schema()
    assert schema.get("type") == "object"
    assert schema.get("additionalProperties") is False
    required = set(schema.get("required") or [])
    props = set((schema.get("properties") or {}).keys())
    assert required == props
    assert "replay_selected" not in props
    assert "online_selected" not in props
    assert (
        schema.get("properties", {})
        .get("diffs", {})
        .get("items", {})
        .get("type")
    ) == "string"


def test_summary_only_output_matches_schema_surface() -> None:
    schema = _load_schema()
    expected_keys = set((schema.get("properties") or {}).keys())
    full_report = {
        "start_ms": 1,
        "end_ms": 2,
        "streams": {"raw": "ec:raw", "selected": "ec:selected"},
        "stream_presence": {"raw": "present", "selected": "present"},
        "missing_streams": [],
        "counts": {
            "raw_events": 1,
            "online_selected": 1,
            "replay_selected": 1,
            "replay_layers": {"raw": 1, "normalized": 1, "evidence": 1, "context": 1, "selected": 1},
        },
        "ok": True,
        "ignore_fields": [],
        "signatures": {"replay_selected": "abc", "online_selected": "abc"},
        "selected_contract": {
            "ok": True,
            "errors": [],
            "required_fields": ["asset"],
            "allowed_fields": ["asset"],
            "schema_path": "services/event_center_new/docs/selected_event.schema.json",
        },
        "diffs": [],
        "replay_selected": [{"x": 1}],
        "online_selected": [{"x": 1}],
    }
    summary = _to_summary_report(full_report)
    assert set(summary.keys()) == expected_keys
    assert "replay_selected" not in summary
    assert "online_selected" not in summary
