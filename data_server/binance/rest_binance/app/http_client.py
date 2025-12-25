import aiohttp
import asyncio
from typing import Optional
try:
    from .config import settings
    from .utils import backoff_sleep, logger
except ImportError:
    from config import settings
    from utils import backoff_sleep, logger


class HTTPClient:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session and not self._session.closed:
            return self._session
        async with self._lock:
            if self._session and not self._session.closed:
                return self._session
            timeout = aiohttp.ClientTimeout(total=settings.http_timeout_s)
            self._session = aiohttp.ClientSession(timeout=timeout, trust_env=False)
            return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def request(self, method: str, url: str, params: dict = None, headers: dict = None, json: dict = None, max_retries: int = 3, ssl=False, proxy: str = None):
        attempt = 0
        session = await self.get_session()
        while True:
            try:
                _proxy = proxy if proxy is not None else (settings.http_proxy if settings.proxy_mode else None)
                if isinstance(_proxy, dict):
                    if url.startswith("https"):
                        _proxy = _proxy.get("https") or _proxy.get("http")
                    else:
                        _proxy = _proxy.get("http") or _proxy.get("https")
                async with session.request(method, url, params=params, headers=headers, json=json, ssl=ssl, proxy=_proxy) as resp:
                    status = resp.status
                    if 200 <= status < 300:
                        return await resp.json()
                    if status in (429, 502, 503, 504):
                        text = await resp.text()
                        raise aiohttp.ClientResponseError(resp.request_info, resp.history, status=status, message=text)
                    text = await resp.text()
                    logger.warning("non_retryable_http_status %s %s", status, url)
                    return {"status": status, "text": text}
            except Exception as e:
                logger.exception("http_request_failed attempt=%s method=%s url=%s error=%s", attempt, method, url, e)
                if attempt >= max_retries:
                    raise
                await backoff_sleep(attempt)
                attempt += 1


http_client = HTTPClient()
