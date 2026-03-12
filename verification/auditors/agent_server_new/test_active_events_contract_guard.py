from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent_server_new.adapters.active_events_redis import RedisActiveEventsProvider


def _load_selected_schema() -> dict:
    path = Path(PROJECT_ROOT) / "event_center_new" / "docs" / "selected_event.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_agent_consumer_depends_on_selected_event_core_fields() -> None:
    schema = _load_selected_schema()
    required = set(schema.get("required") or [])
    # 中文注释：这里冻结 agent 对 event_center selected_event 的最小依赖面。
    assert {"asset", "selected_type", "direction_hint", "priority", "context_snapshot", "route"} <= required


def test_agent_active_events_minimal_schema_is_stable() -> None:
    selected_payload = {
        "asset": "binance:ETHUSDT",
        "selected_type": "event.selected",
        "direction_hint": "bearish",
        "priority": "medium",
        "source": "event_center_new",
        "trace": {"schema_version": "selected-v2"},
        "context_snapshot": {"why": "contract-guard"},
        "route": {"horizon": "15m"},
    }
    normalized = RedisActiveEventsProvider._normalize_active_event(  # noqa: SLF001
        selected_payload,
        stream_id="123-0",
        exchange="binance",
        symbol="ETHUSDT",
    )
    assert set(normalized.keys()) == {"event_id", "source", "type", "asset", "direction", "score", "timeframe", "evidence"}
    assert normalized["type"] == "event.selected"
    assert normalized["direction"] == "bearish"
    assert normalized["score"] == 0.6
    assert normalized["source"] == "event_center_new"
    assert dict(normalized["evidence"]).get("trace", {}).get("schema_version") == "selected-v2"
