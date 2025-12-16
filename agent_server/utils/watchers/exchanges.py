import asyncio
from typing import Set
import redis.asyncio as aioredis


class RedisExchangeWatcher:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    async def list_exchanges(self) -> Set[str]:
        exchanges: Set[str] = set()
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(cursor=cursor, match="symbol:*", count=1000)
            for k in keys or []:
                try:
                    t = await self.redis.type(k)
                    if isinstance(t, (bytes, bytearray)):
                        t = t.decode()
                    if t == "set" and k.startswith("symbol:"):
                        exchanges.add(k.split(":", 1)[1])
                except Exception:
                    continue
            if cursor == 0:
                break
        return exchanges

    async def watch_changes(self, poll_interval: float = 1.0):
        prev: Set[str] = set()
        while True:
            try:
                cur = await self.list_exchanges()
                if cur != prev:
                    yield cur
                    prev = cur
                await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(poll_interval)

