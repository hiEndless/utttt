from .http_client import http_client
from .ratelimiter import TokenBucket
from .utils import logger
from .config import settings


GLOBAL_LIMITER = TokenBucket(rate=settings.api_rate_limit_per_second)


async def fetch_kline(symbol: str):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": "1m", "limit": 1}
    async with GLOBAL_LIMITER:
        data = await http_client.request("GET", url, params=params)
        logger.info("kline %s %s", symbol, data[0] if isinstance(data, list) and data else data)


async def fetch_open_interest(symbol: str):
    url = "https://fapi.binance.com/futures/data/openInterest"
    params = {"symbol": symbol}
    async with GLOBAL_LIMITER:
        data = await http_client.request("GET", url, params=params)
        logger.info("oi %s %s", symbol, data)


async def fetch_funding_rate(symbol: str):
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    params = {"symbol": symbol, "limit": 1}
    async with GLOBAL_LIMITER:
        data = await http_client.request("GET", url, params=params)
        logger.info("funding %s %s", symbol, data[0] if isinstance(data, list) and data else data)