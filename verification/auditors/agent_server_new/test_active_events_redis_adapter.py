import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.active_events_redis import RedisActiveEventsConfig, RedisActiveEventsProvider


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
    assert dict(one["evidence"]).get("event_source") == "event_center_new"
    assert dict(one["evidence"]).get("inference_source") == "event_center_new.selector"
    assert dict(one["evidence"]).get("event_ts_ms") is None
    assert dict(one["evidence"]).get("processed_ts_ms") is None


def test_redis_active_events_provider_normalizes_source_object():
    rows = [
        (
            "12-0",
            {
                "payload": json.dumps(
                    {
                        "asset": "binance:ETHUSDT",
                        "selected_type": "event.selected",
                        "direction_hint": "mixed",
                        "priority": "medium",
                        "source": {"name": "news_feed", "category": "news"},
                        "trace": {"schema_version": "selected-v2", "produced_by": "event_center_new.selector"},
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
    assert one["source"] == "news_feed"
    evidence = dict(one["evidence"])
    assert evidence.get("event_source") == "news_feed"
    assert evidence.get("event_source_category") == "news"
    assert evidence.get("inference_source") == "event_center_new.selector"


def test_redis_active_events_provider_infers_source_category_from_source_name() -> None:
    rows = [
        (
            "13-0",
            {
                "payload": json.dumps(
                    {
                        "asset": "binance:ETHUSDT",
                        "selected_type": "event.selected",
                        "source": "x_twitter_stream",
                        "context_snapshot": {"reason": "social-event"},
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
    evidence = dict(out[0]["evidence"])
    assert evidence.get("event_source") == "x_twitter_stream"
    assert evidence.get("event_source_category") == "social"


def test_redis_active_events_provider_prefers_explicit_source_category() -> None:
    rows = [
        (
            "14-0",
            {
                "payload": json.dumps(
                    {
                        "asset": "binance:ETHUSDT",
                        "selected_type": "event.selected",
                        "source": "coindesk_feed",
                        "source_category": "onchain",
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
    evidence = dict(out[0]["evidence"])
    assert evidence.get("event_source") == "coindesk_feed"
    assert evidence.get("event_source_category") == "onchain"


def test_redis_active_events_provider_time_semantics_precedence_and_fallback():
    rows = [
        (
            "10-0",
            {
                "payload": json.dumps(
                    {
                        "asset": "binance:ETHUSDT",
                        "selected_type": "event.selected",
                        "event_ts_ms": 1710000000001,
                        "processed_ts_ms": 1710000000009,
                        "ts_ms": 1710000000000,
                    }
                )
            },
        ),
        (
            "11-0",
            {
                "payload": json.dumps(
                    {
                        "asset": "binance:ETHUSDT",
                        "selected_type": "event.selected",
                        "ts_ms": 1710000001000,
                    }
                )
            },
        ),
    ]
    provider = RedisActiveEventsProvider(
        client=_FakeRedis(rows),
        cfg=RedisActiveEventsConfig(stream="ec:selected", limit_default=5, scan_factor=2),
    )
    out = asyncio.run(provider.get_active_events("binance", "ETHUSDT"))
    assert len(out) == 2

    first = dict(out[0]["evidence"])
    assert first["event_ts_ms"] == 1710000000001
    assert first["processed_ts_ms"] == 1710000000009

    second = dict(out[1]["evidence"])
    assert second["event_ts_ms"] == 1710000001000
    assert second["processed_ts_ms"] == 1710000001000
