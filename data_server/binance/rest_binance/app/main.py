import asyncio
import signal
import logging
import redis.asyncio as aioredis
from .config import settings
from .manager import SymbolTaskManager
from .redis_watch import RedisSymbolWatcher
from .fetchers import fetch_kline, fetch_open_interest, fetch_funding_rate
from .http_client import http_client
from .utils import logger


FETCH_PLAN = [
    {"name": "kline", "fn": fetch_kline, "interval": 1.0},
    {"name": "open_interest", "fn": fetch_open_interest, "interval": 5.0},
    {"name": "funding", "fn": fetch_funding_rate, "interval": 10.0},
]


async def _run():
    redis = aioredis.Redis(host=settings.redis_host, password=settings.redis_password, port=settings.redis_port, db=settings.redis_db, decode_responses=True)
    watcher = RedisSymbolWatcher(redis)
    manager = SymbolTaskManager()
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _on_sig(*_):
        logger.info("received_stop_signal")
        stop.set()

    loop.add_signal_handler(signal.SIGINT, _on_sig)
    loop.add_signal_handler(signal.SIGTERM, _on_sig)

    try:
        async for symbols in watcher.watch_changes():
            cur = set(manager.list_symbols())
            for s in symbols - cur:
                await manager.start_symbol(s, FETCH_PLAN)
            for s in cur - symbols:
                await manager.stop_symbol(s)
            if stop.is_set():
                break
            await asyncio.sleep(0.1)
    finally:
        for s in manager.list_symbols():
            await manager.stop_symbol(s)
        await http_client.close()
        await redis.close()


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    asyncio.run(_run())


if __name__ == "__main__":
    main()