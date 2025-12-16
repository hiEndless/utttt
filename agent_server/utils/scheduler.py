import time
import asyncio
from typing import Callable


async def run_interval(interval: float, coro: Callable, *args, stop_event: asyncio.Event = None):
    next_run = time.monotonic()
    while True:
        if stop_event and stop_event.is_set():
            break
        next_run += interval
        try:
            await coro(*args)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        sleep_time = next_run - time.monotonic()
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
        else:
            next_run = time.monotonic()
