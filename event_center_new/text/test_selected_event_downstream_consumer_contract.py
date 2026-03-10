from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent_server_new.adapters.active_events_redis import RedisActiveEventsProvider


def _load_selected_schema() -> dict:
    path = Path(PROJECT_ROOT) / "event_center_new" / "docs" / "selected_event.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_selected_event_schema_keeps_downstream_mapping_core_fields() -> None:
    schema = _load_selected_schema()
    required = set(schema.get("required") or [])
    # 中文注释：冻结对下游 active_events 映射的最小字段依赖面。
    assert {"asset", "selected_type", "direction_hint", "priority", "context_snapshot", "trace", "route"} <= required


def test_selected_event_can_map_to_agent_active_events_shape() -> None:
    selected = {
        "asset": "binance:ETHUSDT",
        "ts_ms": 1710000000000,
        "selected_type": "event.selected",
        "direction_hint": "mixed",
        "priority": "medium",
        "context_snapshot": {"conflicts": [{"kind": "direction_conflict"}]},
        "trace": {"schema_version": "selected-v2"},
        "route": {"horizon": "15m"},
    }
    normalized = RedisActiveEventsProvider._normalize_active_event(  # noqa: SLF001
        selected,
        stream_id="ec-selected-1",
        exchange="binance",
        symbol="ETHUSDT",
    )
    assert set(normalized.keys()) == {"event_id", "source", "type", "asset", "direction", "score", "timeframe", "evidence"}
    assert normalized["type"] == "event.selected"
    assert normalized["direction"] == "mixed"
    assert normalized["score"] == 0.6
    assert normalized["timeframe"] == "15m"
    assert dict(normalized["evidence"]).get("conflicts") == [{"kind": "direction_conflict"}]
    assert dict(normalized["evidence"]).get("trace", {}).get("schema_version") == "selected-v2"
