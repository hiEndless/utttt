import asyncio
from typing import Dict, List
from agent_server.utils.scheduler import run_interval
import logging
import os


logger = logging.getLogger("background")


class SymbolTaskManager:
    def __init__(self):
        self._groups: Dict[str, Dict[str, Dict]] = {}
        self._lock = asyncio.Lock()
        # 中文注释：限制后台任务并发，避免瞬时请求过多导致 API/Redis 报 Too many connections
        self._max_concurrency = int(os.environ.get("BACKGROUND_TASK_CONCURRENCY", 5))
        self._sem = asyncio.Semaphore(max(self._max_concurrency, 1))

    async def start_symbol(self, symbol: str, fetch_plan: List[Dict]):
        async with self._lock:
            if symbol in self._groups:
                logger.debug("symbol_already_running %s", symbol)
                return
            stop_event = asyncio.Event()
            tasks = {}
            for item in fetch_plan:
                name = item["name"]
                fn = item["fn"]
                interval = item["interval"]

                async def runner(fn=fn, symbol=symbol, name=name):
                    try:
                        async with self._sem:
                            await fn(symbol)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.exception("background_task_crashed %s %s", name, symbol)
                        raise

                # 中文注释：通过稳定抖动打散同一时刻启动的任务，减少启动瞬间的请求尖峰
                task = asyncio.create_task(
                    run_interval(
                        interval,
                        runner,
                        stop_event=stop_event,
                        jitter_seed=f"{symbol}:{name}",
                    ),
                    name=f"{symbol}:{name}",
                )
                tasks[name] = {"task": task}

            self._groups[symbol] = {"stop_event": stop_event, "tasks": tasks}
            logger.info("started_symbol %s %d", symbol, len(tasks))

    async def stop_symbol(self, symbol: str):
        async with self._lock:
            info = self._groups.get(symbol)
            if not info:
                return
            info["stop_event"].set()
            for name, entry in info["tasks"].items():
                entry["task"].cancel()
            await asyncio.gather(*[e["task"] for e in info["tasks"].values()], return_exceptions=True)
            del self._groups[symbol]
            logger.info("stopped_symbol %s", symbol)

    def list_symbols(self):
        return list(self._groups.keys())
