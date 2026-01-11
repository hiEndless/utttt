import asyncio
import signal
import logging
import time
import sys
import os
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
    logger.info("=" * 60)
    logger.info("data_server/binance/rest_binance 服务启动中...")
    logger.info("=" * 60)
    
    # 打印 Redis 配置信息（不打印密码）
    logger.info("Redis 配置: host=%s port=%d db=%d password=%s", 
                settings.redis_host, 
                settings.redis_port, 
                settings.redis_db,
                "***" if settings.redis_password else "None")
    
    # 连接 Redis
    logger.info("正在连接 Redis...")
    redis = aioredis.Redis(host=settings.redis_host, password=settings.redis_password, port=settings.redis_port,
                           db=settings.redis_db, decode_responses=True)
    
    # 测试 Redis 连接
    try:
        pong = await redis.ping()
        logger.info("Redis 连接成功: PING=%s", pong)
    except Exception as e:
        logger.error("Redis 连接失败: %s", e)
        raise
    
    watcher = RedisSymbolWatcher(redis)
    manager = SymbolTaskManager()
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _on_sig(*_):
        logger.info("收到停止信号 (SIGINT/SIGTERM)")
        stop.set()

    loop.add_signal_handler(signal.SIGINT, _on_sig)
    loop.add_signal_handler(signal.SIGTERM, _on_sig)
    
    logger.info("信号处理器已注册: SIGINT, SIGTERM")
    logger.info("开始监听符号变化 (监控集合: %s)", watcher.monitor_set)
    logger.info("已配置的采集任务: %s", [item["name"] for item in FETCH_PLAN])
    logger.info("-" * 60)

    try:
        async for symbols in watcher.watch_changes():
            cur = set(manager.list_symbols())
            new_symbols = symbols - cur
            removed_symbols = cur - symbols
            
            if new_symbols:
                logger.info("检测到新符号: %s (总数: %d)", list(new_symbols), len(symbols))
                for s in new_symbols:
                    await manager.start_symbol(s, FETCH_PLAN)
            
            if removed_symbols:
                logger.info("检测到符号移除: %s (剩余: %d)", list(removed_symbols), len(symbols))
                for s in removed_symbols:
                    await manager.stop_symbol(s)
            
            if not new_symbols and not removed_symbols and symbols:
                logger.debug("当前监控符号: %s (总数: %d)", list(symbols), len(symbols))
            
            if stop.is_set():
                logger.info("收到停止信号，开始关闭服务...")
                break
            await asyncio.sleep(0.1)
    except Exception as e:
        logger.exception("服务运行异常: %s", e)
        raise
    finally:
        logger.info("-" * 60)
        logger.info("开始清理资源...")
        running_symbols = manager.list_symbols()
        if running_symbols:
            logger.info("正在停止 %d 个符号的采集任务: %s", len(running_symbols), running_symbols)
            for s in running_symbols:
                await manager.stop_symbol(s)
        logger.info("正在关闭 HTTP 客户端...")
        await http_client.close()
        logger.info("正在关闭 Redis 连接...")
        await redis.aclose()
        logger.info("服务已完全关闭")
        logger.info("=" * 60)


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    
    # 打印启动信息
    script_path = os.path.abspath(__file__)
    logger.info("=" * 60)
    logger.info("启动脚本: %s", script_path)
    logger.info("工作目录: %s", os.getcwd())
    logger.info("Python 版本: %s", sys.version.split()[0])
    logger.info("日志级别: %s", settings.log_level)
    logger.info("=" * 60)
    
    asyncio.run(_run())


if __name__ == "__main__":
    main()
