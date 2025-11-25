import asyncio

try:
    from .http_client import http_client
    from .ratelimiter import TokenBucket
    from .utils import logger
    from .config import settings
except ImportError:
    from http_client import http_client
    from ratelimiter import TokenBucket
    from utils import logger
    from config import settings

KLINE_LIMITER = TokenBucket(rate=1 / settings.rate_limits['kline'], capacity=1)
OPEN_INTEREST_LIMITER = TokenBucket(rate=1 / settings.rate_limits['open_interest'], capacity=1)
FUNDING_RATE_LIMITER = TokenBucket(rate=1 / settings.rate_limits['funding'], capacity=1)

BASE_URL = 'https://fapi.binance.com'


async def fetch_kline(symbol: str, interval: str, limit: int = 200):
    url = BASE_URL + '/fapi/v1/klines'
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    async with KLINE_LIMITER:
        data = await http_client.request("GET", url, params=params)
        print(data)
        logger.info("kline %s %s", symbol, data[0] if isinstance(data, list) and data else data)


async def _main():
    try:
        while True:
            try:
                await fetch_kline("BTCUSDT", "1m")
            except Exception as e:
                logger.error("fetch_kline_error %s", e)
    finally:
        await http_client.close()

if __name__ == "__main__":
    asyncio.run(_main())
