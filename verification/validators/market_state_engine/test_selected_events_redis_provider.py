import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.market_state_engine.src.adapters.selected_events_redis import RedisSelectedEventProvider, RedisSelectedEventProviderConfig


class _FakeRedisClient:
    def __init__(self, rows):
        self._rows = rows

    def xrevrange(self, stream, max_id, min_id, count):  # noqa: ANN001
        return list(self._rows)


def test_selected_events_redis_provider_filters_exchange_symbol():
    rows = [
        ("1-0", {"payload": json.dumps({"asset": "binance:ETHUSDT", "selected_type": "breakout_signal"})}),
        ("2-0", {"payload": json.dumps({"asset": "okx:ETHUSDT", "selected_type": "breakout_signal"})}),
    ]
    provider = RedisSelectedEventProvider(
        client=_FakeRedisClient(rows),
        cfg=RedisSelectedEventProviderConfig(stream="ec:selected", limit_default=20, scan_factor=2),
    )

    out = asyncio.run(provider.get_selected_events("binance", "ETHUSDT", limit=10))
    assert len(out) == 1
    assert out[0]["asset"] == "binance:ETHUSDT"


def test_selected_events_redis_provider_ignores_invalid_payload():
    rows = [
        ("1-0", {"payload": "not-json"}),
        ("2-0", {"payload": json.dumps({"asset": "", "selected_type": "x"})}),
    ]
    provider = RedisSelectedEventProvider(client=_FakeRedisClient(rows))

    out = asyncio.run(provider.get_selected_events("binance", "ETHUSDT", limit=10))
    assert out == []


def test_selected_events_redis_provider_exact_match_only():
    rows = [
        ("1-0", {"payload": json.dumps({"asset": "binance:ETHUSDT", "selected_type": "ok"})}),
        ("2-0", {"payload": json.dumps({"asset": "binance:ETH", "selected_type": "bad_substring"})}),
        ("3-0", {"payload": json.dumps({"asset": "ETHUSDT", "selected_type": "ok_symbol_only"})}),
        ("4-0", {"payload": json.dumps({"asset": "BINANCE:ethusdt", "selected_type": "ok_case_insensitive"})}),
    ]
    provider = RedisSelectedEventProvider(client=_FakeRedisClient(rows))

    out = asyncio.run(provider.get_selected_events("binance", "ETHUSDT", limit=10))
    assets = [str(x.get("asset")) for x in out]
    assert "binance:ETH" not in assets
    assert "binance:ETHUSDT" in assets
    assert "ETHUSDT" in assets
    assert "BINANCE:ethusdt" in assets
