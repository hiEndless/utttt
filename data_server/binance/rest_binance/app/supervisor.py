import asyncio
from typing import Callable
from utils import logger, backoff_sleep


async def supervise_task(make_coro: Callable, name: str, max_restarts: int = 5):
    restarts = 0
    while True:
        try:
            coro = make_coro()
            await coro
            logger.info("task_exited_normally %s", name)
            return
        except asyncio.CancelledError:
            logger.info("task_cancelled %s", name)
            raise
        except Exception:
            logger.exception("task_crashed %s", name)
            if restarts >= max_restarts:
                logger.error("task_exceeded_max_restarts %s %s", name, max_restarts)
                return
            await backoff_sleep(restarts)
            restarts += 1
            logger.info("task_restarting %s %s", name, restarts)