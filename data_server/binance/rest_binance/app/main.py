import asyncio
import signal
import logging
import time
import redis.asyncio as aioredis
from config import settings
from manager import SymbolTaskManager
from redis_watch import RedisSymbolWatcher
from fetchers import (
    fetch_kline,
    fetch_takerlongshortRatio,
    fetch_topLongShortAccountRatio,
    fetch_topLongShortPositionRatio,
    fetch_globalLongShortAccountRatio,
    fetch_ticker24hr,
    fetch_fundingRate,
)
from http_client import http_client
from utils import logger


def make_spider(interval: str, limit: int = 300):
    async def run(symbol: str):
        logger.info("task_trigger name=%s interval=%s time=%s", f"spider_{interval}", interval,
                    time.strftime("%Y-%m-%d %H:%M:%S"))
        await fetch_kline(symbol, interval, limit)
        await fetch_takerlongshortRatio(symbol, interval)
        await fetch_topLongShortAccountRatio(symbol, interval)
        await fetch_topLongShortPositionRatio(symbol, interval)
        await fetch_globalLongShortAccountRatio(symbol, interval)

    return run


async def ticker24hr_task(symbol: str):
    logger.info("task_trigger name=%s interval=%s time=%s", "ticker24hr", "1h", time.strftime("%Y-%m-%d %H:%M:%S"))
    await fetch_ticker24hr(symbol)


async def fundingRate_task(symbol: str):
    logger.info("task_trigger name=%s interval=%s time=%s", "fundingRate", "4h", time.strftime("%Y-%m-%d %H:%M:%S"))
    await fetch_fundingRate(symbol)


FETCH_PLAN = [
    {"name": "spider_1m", "fn": make_spider("1m"), "interval": settings.rate_limits_seconds["1m"]},
    {"name": "spider_30m", "fn": make_spider("30m"), "interval": settings.rate_limits_seconds["30m"]},
    {"name": "spider_1h", "fn": make_spider("1h"), "interval": settings.rate_limits_seconds["1h"]},
    {"name": "spider_2h", "fn": make_spider("2h"), "interval": settings.rate_limits_seconds["2h"]},
    {"name": "spider_4h", "fn": make_spider("4h"), "interval": settings.rate_limits_seconds["4h"]},
    {"name": "spider_1d", "fn": make_spider("1d"), "interval": settings.rate_limits_seconds["1d"]},
    {"name": "ticker24hr", "fn": ticker24hr_task, "interval": settings.rate_limits_seconds["1h"]},
    {"name": "fundingRate", "fn": fundingRate_task, "interval": settings.rate_limits_seconds["4h"]},
]


async def _run():
    redis = aioredis.Redis(host=settings.redis_host, password=settings.redis_password, port=settings.redis_port,
                           db=settings.redis_db, decode_responses=True)
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
