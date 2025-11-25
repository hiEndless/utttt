import asyncio
import time


class TokenBucket:
    def __init__(self, rate: float = 10.0, capacity: float = None):
        self.rate = rate
        self.capacity = capacity or rate
        self._tokens = self.capacity
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last
        self._last = now
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)

    async def acquire(self):
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
            await asyncio.sleep(0.001)

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False