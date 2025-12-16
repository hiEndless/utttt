import aiohttp
import asyncio
from typing import Optional


class HTTPClient:
    def __init__(self, timeout_s: int = 10):
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        self._timeout_s = timeout_s

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session and not self._session.closed:
            return self._session
        async with self._lock:
            if self._session and not self._session.closed:
                return self._session
            timeout = aiohttp.ClientTimeout(total=self._timeout_s)
            self._session = aiohttp.ClientSession(timeout=timeout)
            return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def request(self, method: str, url: str, params: dict = None, headers: dict = None, json: dict = None, max_retries: int = 3, ssl=False):
        attempt = 0
        session = await self.get_session()
        while True:
            try:
                async with session.request(method, url, params=params, headers=headers, json=json, ssl=ssl) as resp:
                    status = resp.status
                    if 200 <= status < 300:
                        ct = resp.headers.get("Content-Type", "")
                        if "application/json" in ct:
                            return await resp.json()
                        return {"status": status, "text": await resp.text()}
                    if status in (429, 502, 503, 504):
                        text = await resp.text()
                        raise aiohttp.ClientResponseError(resp.request_info, resp.history, status=status, message=text)
                    text = await resp.text()
                    return {"status": status, "text": text}
            except Exception:
                if attempt >= max_retries:
                    raise
                await asyncio.sleep(min(2 ** attempt, 5))
                attempt += 1


http_client = HTTPClient()
