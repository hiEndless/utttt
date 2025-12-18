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
            timeout = aiohttp.ClientTimeout(total=settings.http_timeout_s,
                                            connect=10)
            # 创建 SSL 上下文，允许不验证证书（仅用于测试环境）
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl=ssl_context,
                                             limit=100,
                                             limit_per_host=30)
            self._session = aiohttp.ClientSession(timeout=timeout,
                                                  connector=connector)
            return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def request(self,
                      method: str,
                      url: str,
                      params: dict = None,
                      headers: dict = None,
                      json: dict = None,
                      max_retries: int = 3,
                      ssl=None,
                      timeout: int = None):
        attempt = 0
        # 使用自定义超时或默认超时
        request_timeout = timeout or settings.http_timeout_s

        while True:
            try:
                # 每次重试都创建新的 session，确保超时设置生效
                session = await self.get_session()
                # 如果超时时间不同，创建新的 session
                if request_timeout != settings.http_timeout_s:
                    import ssl as ssl_module
                    timeout_obj = aiohttp.ClientTimeout(total=request_timeout,
                                                        connect=10)
                    ssl_context = ssl_module.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl_module.CERT_NONE
                    connector = aiohttp.TCPConnector(ssl=ssl_context,
                                                     limit=100,
                                                     limit_per_host=30)
                    async with aiohttp.ClientSession(
                            timeout=timeout_obj,
                            connector=connector) as temp_session:
                        async with temp_session.request(method,
                                                        url,
                                                        params=params,
                                                        headers=headers,
                                                        json=json) as resp:
                            status = resp.status
                            if 200 <= status < 300:
                                return await resp.json()
                            if status in (429, 502, 503, 504):
                                text = await resp.text()
                                raise aiohttp.ClientResponseError(
                                    resp.request_info,
                                    resp.history,
                                    status=status,
                                    message=text)
                            text = await resp.text()
                            logger.warning("non_retryable_http_status %s %s",
                                           status, url)
                            return {"status": status, "text": text}
                else:
                    async with session.request(method,
                                               url,
                                               params=params,
                                               headers=headers,
                                               json=json) as resp:
                        status = resp.status
                        if 200 <= status < 300:
                            return await resp.json()
                        if status in (429, 502, 503, 504):
                            text = await resp.text()
                            raise aiohttp.ClientResponseError(
                                resp.request_info,
                                resp.history,
                                status=status,
                                message=text)
                        text = await resp.text()
                        logger.warning("non_retryable_http_status %s %s",
                                       status, url)
                        return {"status": status, "text": text}
            except (asyncio.TimeoutError, aiohttp.ServerTimeoutError,
                    aiohttp.ClientError) as e:
                # 超时和网络错误可以重试
                logger.warning(
                    "http_request_timeout_or_error attempt=%s/%s method=%s url=%s error=%s",
                    attempt + 1, max_retries, method, url,
                    str(e)[:100])
                if attempt >= max_retries:
                    logger.error(
                        "http_request_failed_after_retries method=%s url=%s",
                        method, url)
                    raise
                await backoff_sleep(attempt)
                attempt += 1
            except Exception as e:
                # 其他错误也记录并重试
                logger.warning(
                    "http_request_failed attempt=%s/%s method=%s url=%s error=%s",
                    attempt + 1, max_retries, method, url,
                    str(e)[:100])
                if attempt >= max_retries:
                    logger.error(
                        "http_request_failed_after_retries method=%s url=%s error=%s",
                        method, url,
                        str(e)[:100])
                    raise
                await backoff_sleep(attempt)
                attempt += 1


http_client = HTTPClient()
