import time
import asyncio
from typing import Callable
import os
import zlib


def _stable_jitter_delay(seed: str, window_s: float) -> float:
    if not window_s or window_s <= 0:
        return 0.0
    h = zlib.adler32(seed.encode("utf-8")) & 0xFFFFFFFF
    return (h % 1000) / 1000.0 * window_s


async def run_interval(
    interval: float,
    coro: Callable,
    *args,
    stop_event: asyncio.Event = None,
    initial_delay: float = 0.0,
    jitter_seed: str | None = None,
):
    jitter_window = float(os.environ.get("BACKGROUND_TASK_START_JITTER_S", "0") or 0)
    if jitter_seed:
        initial_delay = float(initial_delay or 0) + _stable_jitter_delay(jitter_seed, jitter_window)
    # 中文注释：首次执行前做抖动延迟，避免大量 symbol/interval 在同一时刻同时请求导致下游被打爆
    if initial_delay and initial_delay > 0:
        await asyncio.sleep(initial_delay)
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
