import asyncio
import logging
import os
import signal
import redis.asyncio as aioredis
from agent_server.config import settings
from agent_server.utils.watchers.symbols import RedisSymbolWatcher
from agent_server.utils.watchers.exchanges import RedisExchangeWatcher
from agent_server.utils.manager import SymbolTaskManager
from agent_server.utils.background_tasks import build_fetch_plan


async def _start_exchange_loop(redis: aioredis.Redis, exchange: str, stop_event: asyncio.Event):
    watcher = RedisSymbolWatcher(redis, exchange=exchange)
    manager = SymbolTaskManager()
    fetch_plan = build_fetch_plan(exchange)
    try:
        async for symbols in watcher.watch_changes():
            if stop_event.is_set():
                break
            cur = set(manager.list_symbols())
            for s in symbols - cur:
                await manager.start_symbol(s, fetch_plan)
            for s in cur - symbols:
                await manager.stop_symbol(s)
            await asyncio.sleep(0.1)
    finally:
        for s in manager.list_symbols():
            await manager.stop_symbol(s)


async def _run():
    password = settings.redis_password
    if isinstance(password, str) and password.strip().lower() in ("none", "null", "undefined", ""):
        password = None
    # 中文注释：显式限制连接池，避免高并发时 Redis 连接数暴涨触发 Too many connections
    max_connections = int(os.environ.get("REDIS_MAX_CONNECTIONS", 20))
    pool = aioredis.ConnectionPool(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=password,
        decode_responses=True,
        max_connections=max_connections,
    )
    redis = aioredis.Redis(connection_pool=pool)
    ex_watcher = RedisExchangeWatcher(redis)
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _on_sig(*_):
        logging.getLogger("background").info("received_stop_signal")
        stop.set()

    loop.add_signal_handler(signal.SIGINT, _on_sig)
    loop.add_signal_handler(signal.SIGTERM, _on_sig)

    exchange_tasks: dict[str, dict] = {}

    try:
        async for exchanges in ex_watcher.watch_changes():
            cur = set(exchange_tasks.keys())
            # start new exchange loops
            for ex in exchanges - cur:
                ex_stop = asyncio.Event()
                task = asyncio.create_task(_start_exchange_loop(redis, ex, ex_stop), name=f"exchange:{ex}")
                exchange_tasks[ex] = {"task": task, "stop": ex_stop}
                logging.getLogger("background").info("started_exchange_loop %s", ex)
            # stop removed exchange loops
            for ex in cur - exchanges:
                info = exchange_tasks.get(ex)
                if info:
                    info["stop"].set()
                    info["task"].cancel()
                    await asyncio.gather(info["task"], return_exceptions=True)
                    del exchange_tasks[ex]
                    logging.getLogger("background").info("stopped_exchange_loop %s", ex)
            if stop.is_set():
                break
            await asyncio.sleep(0.2)
    finally:
        for ex, info in list(exchange_tasks.items()):
            info["stop"].set()
            info["task"].cancel()
            await asyncio.gather(info["task"], return_exceptions=True)
        exchange_tasks.clear()
        # 关闭全局 HTTPClient（如果本进程内使用过），避免退出时资源泄漏警告
        from agent_server.utils.http_client import http_client

        await http_client.close()
        await redis.aclose()


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    asyncio.run(_run())


if __name__ == "__main__":
    main()
