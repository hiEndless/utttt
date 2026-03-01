import asyncio
import signal
import logging
import time
import json
import redis.asyncio as aioredis
from config import settings
from manager import SymbolTaskManager
from utils.redis_watch import RedisSymbolWatcher
from fetchers import (
    fetch_kline,
    fetch_takerLongShortRatio,
    fetch_topLongShortAccountRatio,
    fetch_topLongShortPositionRatio,
    fetch_globalLongShortAccountRatio,
    fetch_openInterestHist,
    fetch_openInterest,
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
        if interval != "1m":
            await fetch_takerLongShortRatio(symbol, interval)
            await fetch_topLongShortAccountRatio(symbol, interval)
            await fetch_topLongShortPositionRatio(symbol, interval)
            await fetch_globalLongShortAccountRatio(symbol, interval)
            await fetch_openInterestHist(symbol, interval)

    return run


async def ticker24hr_task(symbol: str):
    logger.info("task_trigger name=%s interval=%s time=%s", "ticker24hr", "1h", time.strftime("%Y-%m-%d %H:%M:%S"))
    await fetch_ticker24hr(symbol)


async def fundingRate_task(symbol: str):
    logger.info("task_trigger name=%s interval=%s time=%s", "fundingRate", "4h", time.strftime("%Y-%m-%d %H:%M:%S"))
    await fetch_fundingRate(symbol)


async def openInterest_task(symbol: str):
    logger.info("task_trigger name=%s interval=%s time=%s", "openInterest", "1m", time.strftime("%Y-%m-%d %H:%M:%S"))
    await fetch_openInterest(symbol)


FETCH_PLAN = [
    {"name": "spider_1m", "fn": make_spider("1m"), "interval": settings.rate_limits_seconds["1m"]},
    {"name": "spider_5m", "fn": make_spider("5m"), "interval": settings.rate_limits_seconds["5m"]},
    {"name": "spider_15m", "fn": make_spider("15m"), "interval": settings.rate_limits_seconds["15m"]},
    {"name": "spider_30m", "fn": make_spider("30m"), "interval": settings.rate_limits_seconds["30m"]},
    {"name": "spider_1h", "fn": make_spider("1h"), "interval": settings.rate_limits_seconds["1h"]},
    {"name": "spider_2h", "fn": make_spider("2h"), "interval": settings.rate_limits_seconds["2h"]},
    {"name": "spider_4h", "fn": make_spider("4h"), "interval": settings.rate_limits_seconds["4h"]},
    {"name": "spider_6h", "fn": make_spider("6h"), "interval": settings.rate_limits_seconds["6h"]},
    {"name": "spider_12h", "fn": make_spider("12h"), "interval": settings.rate_limits_seconds["12h"]},
    {"name": "spider_1d", "fn": make_spider("1d"), "interval": settings.rate_limits_seconds["1d"]},
    {"name": "ticker24hr", "fn": ticker24hr_task, "interval": settings.rate_limits_seconds["1h"]},
    {"name": "fundingRate", "fn": fundingRate_task, "interval": settings.rate_limits_seconds["4h"]},
    {"name": "openInterest", "fn": openInterest_task, "interval": settings.rate_limits_seconds["1m"]},
]


async def _heartbeat(redis: aioredis.Redis, stop: asyncio.Event):
    # 中文注释：写入 rest_binance 心跳，供运维接口判断服务是否存活
    interval_s = float(getattr(settings, "health_heartbeat_interval_s", 2.0) or 2.0)
    ttl_s = int(float(getattr(settings, "health_heartbeat_ttl_s", 10) or 10))
    key = "health:binance:rest_binance"
    while not stop.is_set():
        ts_ms = int(time.time() * 1000)
        try:
            await redis.set(key, json.dumps({"ts": ts_ms, "running": True}), ex=ttl_s)
        except Exception:
            pass
        await asyncio.sleep(max(0.5, interval_s))


async def _run():
    redis = aioredis.Redis(host=settings.redis_host, password=settings.redis_password, port=settings.redis_port,
                           db=settings.redis_db, decode_responses=True)
    watcher = RedisSymbolWatcher(redis)
    manager = SymbolTaskManager()
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    heartbeat_task = asyncio.create_task(_heartbeat(redis, stop))

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
        stop.set()
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except Exception:
            pass
        for s in manager.list_symbols():
            await manager.stop_symbol(s)
        await http_client.close()
        await redis.aclose()


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    asyncio.run(_run())


if __name__ == "__main__":
    main()
