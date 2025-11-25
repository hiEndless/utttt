import asyncio
import logging
import random


logger = logging.getLogger("rest_binance")


async def backoff_sleep(attempt: int, base: float = 0.5, cap: float = 30.0):
    delay = min(cap, base * (2 ** attempt))
    jitter = random.random() * delay * 0.1
    await asyncio.sleep(delay + jitter)