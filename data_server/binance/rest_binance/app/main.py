import asyncio
import signal
import logging
import time
import sys
from config import settings
from manager import SymbolTaskManager
from utils.redis_watch import RedisSymbolWatcher
from utils.redis_client import get_redis_client, _BATCH_WRITERS
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
        logger.info("task_trigger name=%s interval=%s time=%s",
                    f"spider_{interval}", interval,
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
    logger.info("task_trigger name=%s interval=%s time=%s", "ticker24hr", "1h",
                time.strftime("%Y-%m-%d %H:%M:%S"))
    await fetch_ticker24hr(symbol)


async def fundingRate_task(symbol: str):
    logger.info("task_trigger name=%s interval=%s time=%s", "fundingRate",
                "4h", time.strftime("%Y-%m-%d %H:%M:%S"))
    await fetch_fundingRate(symbol)


async def openInterest_task(symbol: str):
    logger.info("task_trigger name=%s interval=%s time=%s", "openInterest",
                "1m", time.strftime("%Y-%m-%d %H:%M:%S"))
    await fetch_openInterest(symbol)


FETCH_PLAN = [
    {
        "name": "spider_1m",
        "fn": make_spider("1m"),
        "interval": settings.rate_limits_seconds["1m"]
    },
    {
        "name": "spider_5m",
        "fn": make_spider("5m"),
        "interval": settings.rate_limits_seconds["5m"]
    },
    {
        "name": "spider_15m",
        "fn": make_spider("15m"),
        "interval": settings.rate_limits_seconds["15m"]
    },
    {
        "name": "spider_30m",
        "fn": make_spider("30m"),
        "interval": settings.rate_limits_seconds["30m"]
    },
    {
        "name": "spider_1h",
        "fn": make_spider("1h"),
        "interval": settings.rate_limits_seconds["1h"]
    },
    {
        "name": "spider_2h",
        "fn": make_spider("2h"),
        "interval": settings.rate_limits_seconds["2h"]
    },
    {
        "name": "spider_4h",
        "fn": make_spider("4h"),
        "interval": settings.rate_limits_seconds["4h"]
    },
    {
        "name": "spider_4h",
        "fn": make_spider("6h"),
        "interval": settings.rate_limits_seconds["6h"]
    },
    {
        "name": "spider_4h",
        "fn": make_spider("12h"),
        "interval": settings.rate_limits_seconds["12h"]
    },
    {
        "name": "spider_1d",
        "fn": make_spider("1d"),
        "interval": settings.rate_limits_seconds["1d"]
    },
    {
        "name": "ticker24hr",
        "fn": ticker24hr_task,
        "interval": settings.rate_limits_seconds["1h"]
    },
    {
        "name": "fundingRate",
        "fn": fundingRate_task,
        "interval": settings.rate_limits_seconds["4h"]
    },
    {
        "name": "openInterest",
        "fn": openInterest_task,
        "interval": settings.rate_limits_seconds["1m"]
    },
]


async def _run():
    logger.info("=" * 60)
    logger.info("启动 data_server (rest_binance)")
    logger.info("Redis 配置: host=%s port=%s db=%s", settings.redis_host,
                settings.redis_port, settings.redis_db)

    # 使用统一的 Redis 客户端管理，避免连接数过多
    try:
        redis = get_redis_client(db=settings.redis_db, decode_responses=True)
        # 测试 Redis 连接
        await redis.ping()
        logger.info("Redis 连接成功")
    except Exception as e:
        logger.error("Redis 连接失败: %s", e)
        raise

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
        # Windows 平台使用 signal.signal() 作为替代方案
        signal.signal(signal.SIGINT, lambda s, f: stop.set())
        if sys.platform != 'win32':
            signal.signal(signal.SIGTERM, lambda s, f: stop.set())

    # 初始化时检查一次符号列表
    try:
        initial_symbols = await watcher.list_symbols()
        logger.info("当前监控符号: %s (共 %d 个)",
                    list(initial_symbols) if initial_symbols else "无",
                    len(initial_symbols))
        if initial_symbols:
            for s in initial_symbols:
                await manager.start_symbol(s, FETCH_PLAN)
    except Exception as e:
        logger.exception("初始化符号失败: %s", e)

    logger.info("开始监听符号变化...")
    logger.info("提示: 使用 redis-cli 执行 'SADD symbol:binance BTCUSDT' 添加监控符号")
    logger.info("=" * 60)

    try:
        async for symbols in watcher.watch_changes():
            cur = set(manager.list_symbols())
            added = symbols - cur
            removed = cur - symbols

            if added:
                logger.info("检测到新符号: %s (总数: %d)", list(added), len(symbols))
            if removed:
                logger.info("检测到符号移除: %s (剩余: %d)", list(removed),
                            len(symbols))

            for s in added:
                await manager.start_symbol(s, FETCH_PLAN)
            for s in removed:
                await manager.stop_symbol(s)

            if stop.is_set():
                break
            await asyncio.sleep(0.1)
    except Exception as e:
        logger.exception("运行错误: %s", e)
        raise
    finally:
        # 停止所有任务
        for s in manager.list_symbols():
            await manager.stop_symbol(s)

        # 刷新所有批量写入器，确保数据不丢失
        for writer in _BATCH_WRITERS.values():
            try:
                await writer.flush()
                await writer.close()
            except Exception as e:
                logger.exception("batch_writer_close_error %s", e)

        # 关闭 HTTP 客户端和 Redis 连接
        await http_client.close()
        await redis.aclose()


def main():
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.exception("程序异常退出: %s", e)
        raise


if __name__ == "__main__":
    main()
