import asyncio
import json

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
    assert out[0]["event_type"] == "selected"
    assert out[1]["event_type"] == "fallback"


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
