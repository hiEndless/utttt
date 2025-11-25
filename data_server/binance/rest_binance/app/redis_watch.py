import asyncio
import redis.asyncio as aioredis
try:
    from .config import settings
except ImportError:
    from config import settings


class RedisSymbolWatcher:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
        self.monitor_set = "symbol:binance"

    async def list_symbols(self):
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


async def _test():
    redis = aioredis.Redis(host=settings.redis_host, password=settings.redis_password, port=settings.redis_port, db=settings.redis_db, decode_responses=True)
    try:
        pong = await redis.ping()
        symbols = await RedisSymbolWatcher(redis).list_symbols()
        print({"ping": pong, "symbols": list(symbols)})
    finally:
        await redis.close()


if __name__ == "__main__":
    asyncio.run(_test())