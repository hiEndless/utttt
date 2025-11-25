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

LIMITERS = {k: TokenBucket(rate=1 / v, capacity=1) for k, v in settings.rate_limits_seconds.items()}

BASE_URL = 'https://fapi.binance.com'


async def fetch_kline(symbol: str, interval: str, limit: int = 200):
    """K线数据"""
    url = BASE_URL + '/fapi/v1/klines'
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    limiter = LIMITERS.get(interval)
    async with limiter:
        data = await http_client.request("GET", url, params=params)
        print(data)


async def fetch_topLongShortAccountRatio(symbol: str, period: str):
    """大户账户数多空比"""
    url = BASE_URL + '/futures/data/topLongShortAccountRatio'
    if period == '1m':
        period = '5m'
    params = {
        'symbol': symbol,
        'period': period,
        'limit': 30
    }
    limiter = LIMITERS.get(period)
    async with limiter:
        res = await http_client.request("GET", url, params=params)
        # todo 首次获取数据整体添加，后续获取做增量更新
        print(res)


async def fetch_topLongShortPositionRatio(symbol: str, period: str):
    """大户持仓多空比"""
    url = BASE_URL + '/futures/data/topLongShortPositionRatio'
    if period == '1m':
        period = '5m'
    params = {
        'symbol': symbol,
        'period': period,
        'limit': 30
    }
    limiter = LIMITERS.get(period)
    async with limiter:
        res = await http_client.request("GET", url, params=params)
        # todo 首次获取数据整体添加，后续获取做增量更新
        print(res)


async def fetch_globalLongShortAccountRatio(symbol: str, period: str):
    """全局账户多空比"""
    url = BASE_URL + '/futures/data/globalLongShortAccountRatio'
    if period == '1m':
        period = '5m'
    params = {
        'symbol': symbol,
        'period': period,
        'limit': 30
    }
    limiter = LIMITERS.get(period)
    async with limiter:
        res = await http_client.request("GET", url, params=params)
        # todo 首次获取数据整体添加，后续获取做增量更新
        print(res)


async def fetch_takerlongshortRatio(symbol: str, period: str):
    """ 合约主动买卖量 """
    url = BASE_URL + '/futures/data/takerlongshortRatio'
    if period == '1m':
        period = '5m'
    params = {
        'symbol': symbol,
        'period': period,
        'limit': 30
    }
    limiter = LIMITERS.get(period)
    async with limiter:
        res = await http_client.request("GET", url, params=params)
        # todo 首次获取数据整体添加，后续获取做增量更新
        print(res)


async def fetch_ticker24hr(symbol: str):
    """24hr价格变动情况"""
    url = BASE_URL + '/fapi/v1/ticker/24hr'
    params = {
        'symbol': symbol
    }
    limiter = LIMITERS.get('1h')
    async with limiter:
        res = await http_client.request("GET", url, params=params)
        priceChangePercent = res.get('priceChangePercent')
        volume = res.get('volume')
        quoteVolume = res.get('quoteVolume')
        highPrice = res.get('highPrice')
        lowPrice = res.get('lowPrice')
        data = {
            'priceChangePercent': priceChangePercent,
            'volume': volume,
            'quoteVolume': quoteVolume,
            'highPrice': highPrice,
            'lowPrice': lowPrice
        }
        print(data)


async def fetch_fundingRate(symbol: str):
    """获取资金费率"""
    url = BASE_URL + '/fapi/v1/fundingRate'
    params = {
        'symbol': symbol,
        'limit': 200
    }
    limiter = LIMITERS.get('4h')
    async with limiter:
        res = await http_client.request("GET", url, params=params)
        # todo 首次获取数据整体添加，后续获取做增量更新
        print(res)


async def spider_poller(symbol: str, interval: str, limit: int = 200):
    while True:
        try:
            await fetch_kline(symbol, interval, limit)
            await fetch_takerlongshortRatio(symbol, interval)
            await fetch_topLongShortAccountRatio(symbol, interval)
            await fetch_topLongShortPositionRatio(symbol, interval)
            await fetch_globalLongShortAccountRatio(symbol, interval)
        except Exception as e:
            logger.error("kline_poller_error interval=%s %s", interval, e)

async def ticker24hr_poller(symbol: str):
    while True:
        try:
            await fetch_ticker24hr(symbol)
        except Exception as e:
            logger.error("ticker24hr_poller_error %s", e)

async def fundingRate_poller(symbol: str):
    while True:
        try:
            await fetch_fundingRate(symbol)
        except Exception as e:
            logger.error("fundingRate_poller_error %s", e)


async def _main():
    try:
        tasks = [
            asyncio.create_task(spider_poller("BTCUSDT", "1m", 200)),
            asyncio.create_task(spider_poller("BTCUSDT", "30m", 200)),
            asyncio.create_task(spider_poller("BTCUSDT", "1h", 200)),
            asyncio.create_task(spider_poller("BTCUSDT", "4h", 200)),
            asyncio.create_task(spider_poller("BTCUSDT", "12h", 200)),
            asyncio.create_task(spider_poller("BTCUSDT", "1d", 200)),
            asyncio.create_task(ticker24hr_poller("BTCUSDT")),
            asyncio.create_task(fundingRate_poller("BTCUSDT")),
        ]
        await asyncio.gather(*tasks)
    finally:
        await http_client.close()


if __name__ == "__main__":
    asyncio.run(_main())
