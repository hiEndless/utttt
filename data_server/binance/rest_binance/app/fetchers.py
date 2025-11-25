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

KLINE_LIMITERS = {k: TokenBucket(rate=1 / v, capacity=1) for k, v in settings.kline_rate_limits_seconds.items()}
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
    limiter = KLINE_LIMITERS.get(interval)
    async with limiter:
        data = await http_client.request("GET", url, params=params)
        print(data)


async def kline_poller(symbol: str, interval: str, limit: int = 200):
    while True:
        try:
            await fetch_kline(symbol, interval, limit)
        except Exception as e:
            logger.error("kline_poller_error interval=%s %s", interval, e)

async def _main():
    try:
        tasks = [
            asyncio.create_task(kline_poller("BTCUSDT", "1m", 200)),
            asyncio.create_task(kline_poller("BTCUSDT", "30m", 200)),
            asyncio.create_task(kline_poller("BTCUSDT", "1h", 200)),
            asyncio.create_task(kline_poller("BTCUSDT", "2h", 200)),
        ]
        await asyncio.gather(*tasks)
    finally:
        await http_client.close()

if __name__ == "__main__":
    asyncio.run(_main())
