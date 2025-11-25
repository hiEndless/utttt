import asyncio
import redis.asyncio as aioredis
from .config import settings


class RedisSymbolWatcher:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
        self.monitor_set = settings.monitor_set

    async def list_symbols(self):
        members = await self.redis.smembers(self.monitor_set)
        return set(members or [])

    async def watch_changes(self, poll_interval: float = 1.0):
        prev = set()
        while True:
            cur = await self.list_symbols()
            if cur != prev:
                yield cur
                prev = cur
            await asyncio.sleep(poll_interval)