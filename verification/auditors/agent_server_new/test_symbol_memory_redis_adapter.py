import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.symbol_memory_redis import RedisSymbolMemoryAdapter


class _FakeRedis:
    def __init__(self) -> None:
        self._kv = {}
        self._lists = {}
        self._ttl = {}
        self._sets = {}

    async def get(self, key: str):
        return self._kv.get(key)

    async def set(self, key: str, value: str) -> None:
        self._kv[key] = value

    async def lpush(self, key: str, value: str) -> None:
        items = self._lists.setdefault(key, [])
        items.insert(0, value)

    async def ltrim(self, key: str, start: int, stop: int) -> None:
        items = list(self._lists.get(key, []))
        self._lists[key] = items[start : stop + 1]

    async def lrange(self, key: str, start: int, stop: int):
        items = list(self._lists.get(key, []))
        return items[start : stop + 1]

    async def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))

    async def expire(self, key: str, ttl: int) -> None:
        self._ttl[key] = int(ttl)

    async def sadd(self, key: str, value: str) -> None:
        bucket = self._sets.setdefault(key, set())
        bucket.add(value)

    async def smembers(self, key: str):
        return set(self._sets.get(key, set()))


def test_redis_symbol_memory_adapter_record_and_read():
    async def _run():
        redis = _FakeRedis()
        adapter = RedisSymbolMemoryAdapter(
            redis_client=redis,  # type: ignore[arg-type]
            ttl_seconds=777,
            raw_topk=3,
        )
        for i in range(5):
            await adapter.record_symbol_memory(
                "binance",
                "ethusdt",
                {
                    "ts": 1000 + i,
                    "event_id": f"evt-{i}",
                    "signal": {"direction": "long", "verdict": "accept"},
                    "plan": {"action": "add", "direction": "long"},
                    "contract_warnings": ["state_features_semantic_contract_missing"] if i >= 3 else [],
                },
            )

        out = await adapter.get_symbol_memory("binance", "ETHUSDT", limit=2)
        assert out["summary"]["event_count"] == 3
        assert out["summary"]["last_decision_ts"] == 1004
        assert out["summary"]["contract_warning_count"] == 2
        assert out["summary"]["contract_warning_event_count"] == 2
        assert len(out["recent"]) == 2
        assert out["recent"][0]["event_id"] == "evt-3"
        assert out["recent"][1]["event_id"] == "evt-4"

        raw_key = "agent:memory:raw:binance:ETHUSDT"
        summary_key = "agent:memory:summary:binance:ETHUSDT"
        index_key = "agent:memory:symbols:index"
        assert redis._ttl[raw_key] == 777
        assert redis._ttl[summary_key] == 777
        assert len(redis._lists[raw_key]) == 3
        assert json.loads(redis._kv[summary_key])["last_plan_action"] == "add"
        assert "binance:ETHUSDT" in redis._sets[index_key]

    asyncio.run(_run())
