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
    fetch_takerLongShortRatio,
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
        await fetch_takerLongShortRatio(symbol, interval)
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
    {"name": "spider_5m", "fn": make_spider("5m"), "interval": settings.rate_limits_seconds["5m"]},
    {"name": "spider_15m", "fn": make_spider("15m"), "interval": settings.rate_limits_seconds["15m"]},
    {"name": "spider_30m", "fn": make_spider("30m"), "interval": settings.rate_limits_seconds["30m"]},
    {"name": "spider_1h", "fn": make_spider("1h"), "interval": settings.rate_limits_seconds["1h"]},
    {"name": "spider_2h", "fn": make_spider("2h"), "interval": settings.rate_limits_seconds["2h"]},
    {"name": "spider_4h", "fn": make_spider("4h"), "interval": settings.rate_limits_seconds["4h"]},
    {"name": "spider_1d", "fn": make_spider("1d"), "interval": settings.rate_limits_seconds["1d"]},
    {"name": "ticker24hr", "fn": ticker24hr_task, "interval": settings.rate_limits_seconds["1h"]},
    {"name": "fundingRate", "fn": fundingRate_task, "interval": settings.rate_limits_seconds["4h"]},
]


async def _run():
    print("=" * 60)
    print("REST API 数据抓取服务启动中...")
    print("=" * 60)
    print(f"Redis 连接: {settings.redis_host}:{settings.redis_port}/{settings.redis_db}")
    
    redis = aioredis.Redis(host=settings.redis_host, password=settings.redis_password, port=settings.redis_port,
                           db=settings.redis_db, decode_responses=True)
    
    # 测试 Redis 连接
    try:
        await redis.ping()
        print("✓ Redis 连接成功")
    except Exception as e:
        print(f"✗ Redis 连接失败: {e}")
        await redis.close()
        return
    
    watcher = RedisSymbolWatcher(redis)
    manager = SymbolTaskManager()
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _on_sig(*_):
        logger.info("received_stop_signal")
        stop.set()

    # Windows 不支持 add_signal_handler，使用 try-except 处理
    try:
        loop.add_signal_handler(signal.SIGINT, _on_sig)
        loop.add_signal_handler(signal.SIGTERM, _on_sig)
    except NotImplementedError:
        # Windows 系统，使用替代方案
        # 在 Windows 上，KeyboardInterrupt 会自然触发
        pass

    print("✓ 服务已启动，正在监控交易对...")
    print("  提示: 请确保 BTCUSDT 已添加到 symbol:binance 集合中")
    print("  使用命令: python add_symbol.py add BTCUSDT")
    print("=" * 60)
    print("按 Ctrl+C 停止服务\n")

    try:
        async for symbols in watcher.watch_changes():
            cur = set(manager.list_symbols())
            
            # 显示当前监控的交易对
            if symbols:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 监控的交易对: {sorted(symbols)}")
            
            for s in symbols - cur:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始抓取数据: {s}")
                await manager.start_symbol(s, FETCH_PLAN)
            for s in cur - symbols:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 停止抓取数据: {s}")
                await manager.stop_symbol(s)
            if stop.is_set():
                break
            await asyncio.sleep(0.1)
    except KeyboardInterrupt:
        print("\n收到停止信号，正在关闭服务...")
    finally:
        print("正在清理资源...")
        for s in manager.list_symbols():
            await manager.stop_symbol(s)
        await http_client.close()
        await redis.close()
        print("服务已停止")


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    asyncio.run(_run())


if __name__ == "__main__":
    main()
