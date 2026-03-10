import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent_server_new.adapters.active_events_redis import RedisActiveEventsConfig, RedisActiveEventsProvider


class _FakeRedis:
    def __init__(self, rows):
        self._rows = rows

    def xrevrange(self, stream, max_id, min_id, count=100):  # noqa: ARG002
        return list(self._rows)[:count]


def test_redis_active_events_provider_matches_asset_and_symbol_fields():
    rows = [
        ("1-0", {"payload": json.dumps({"asset": "binance:BTCUSDT", "event_type": "x"})}),
        ("2-0", {"payload": json.dumps({"asset": "binance:ETHUSDT", "event_type": "selected"})}),
        ("3-0", {"payload": json.dumps({"exchange": "binance", "symbol": "ETHUSDT", "event_type": "fallback"})}),
        ("4-0", {"payload": "not-json"}),
    ]
    provider = RedisActiveEventsProvider(
        client=_FakeRedis(rows),
        cfg=RedisActiveEventsConfig(stream="ec:selected", limit_default=5, scan_factor=2),
    )

    out = asyncio.run(provider.get_active_events("binance", "ETHUSDT"))
    assert len(out) == 2
    assert out[0]["type"] == "selected"
    assert out[1]["type"] == "fallback"
    assert out[0]["direction"] == "neutral"
    assert isinstance(out[0]["score"], float)
    assert set(out[0].keys()) == {"event_id", "source", "type", "asset", "direction", "score", "timeframe", "evidence"}


def test_redis_active_events_provider_applies_limit_default():
    rows = [
        (f"{idx}-0", {"payload": json.dumps({"asset": "binance:ETHUSDT", "event_type": f"e{idx}"})})
        for idx in range(5)
    ]
    provider = RedisActiveEventsProvider(
        client=_FakeRedis(rows),
        cfg=RedisActiveEventsConfig(stream="ec:selected", limit_default=2, scan_factor=5),
    )
    out = asyncio.run(provider.get_active_events("binance", "ETHUSDT"))
    assert len(out) == 2


def test_redis_active_events_provider_normalizes_selected_event_fields():
    rows = [
        (
            "9-0",
            {
                "payload": json.dumps(
                    {
                        "asset": "binance:ETHUSDT",
                        "selected_type": "event.selected",
                        "direction_hint": "bullish",
                        "priority": "high",
                        "source": "event_center_new",
                        "trace": {"schema_version": "selected-v2"},
                        "context_snapshot": {"reason": "test"},
                        "route": {"horizon": "5m"},
                    }
                )
            },
        )
    ]
    provider = RedisActiveEventsProvider(
        client=_FakeRedis(rows),
        cfg=RedisActiveEventsConfig(stream="ec:selected", limit_default=3, scan_factor=2),
    )
    out = asyncio.run(provider.get_active_events("binance", "ETHUSDT"))
    assert len(out) == 1
    one = out[0]
    assert one["event_id"] == "9-0"
    assert one["type"] == "event.selected"
    assert one["direction"] == "bullish"
    assert one["score"] == 0.9
    assert one["timeframe"] == "5m"
    assert dict(one["evidence"]).get("reason") == "test"
    assert one["source"] == "event_center_new"
    assert dict(one["evidence"]).get("trace", {}).get("schema_version") == "selected-v2"
