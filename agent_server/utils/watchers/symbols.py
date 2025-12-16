import asyncio
from typing import Set
import redis.asyncio as aioredis


class RedisSymbolWatcher:
    def __init__(self, redis: aioredis.Redis, exchange: str = "binance"):
        self.redis = redis
        self.exchange = exchange
        self.monitor_set = f"symbol:{exchange}"

    async def list_symbols(self) -> Set[str]:
        try:
            key_type = await self.redis.type(self.monitor_set)
            if isinstance(key_type, (bytes, bytearray)):
                key_type = key_type.decode()
            symbols = set()
            if key_type == "set":
                raw = await self.redis.smembers(self.monitor_set)
                symbols = {str(x) for x in (raw or [])}
            return symbols
        except Exception:
            return set()

    async def watch_changes(self, poll_interval: float = 1.0):
        prev = set()
        while True:
            try:
                cur = await self.list_symbols()
                if cur != prev:
                    yield cur
                    prev = cur
                await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(poll_interval)

