import asyncio

try:
    from .http_client import http_client
    from .ratelimiter import TokenBucket
    from .utils import logger
    from .config import settings
    from .indicators_producer import EventGenerator as IndicatorsProducer
    from .market_store import store_market_raw, store_market_raw_simple
except ImportError:
    from http_client import http_client
    from ratelimiter import TokenBucket
    from utils import logger
    from config import settings
    from indicators_producer import EventGenerator as IndicatorsProducer
    from market_store import store_market_raw, store_market_raw_simple

LIMITERS = {k: TokenBucket(rate=1 / v, capacity=1) for k, v in settings.rate_limits_seconds.items()}
LIMITER_CACHE = {}


def get_limiter(key: tuple, seconds: int):
    lim = LIMITER_CACHE.get(key)
    if lim is None:
        lim = TokenBucket(rate=1 / max(1, seconds), capacity=1)
        LIMITER_CACHE[key] = lim
    return lim


BASE_URL = 'https://fapi.binance.com'


async def fetch_kline(symbol: str, interval: str, limit: int = 200):
    """K线数据"""
    url = BASE_URL + '/fapi/v1/klines'
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    _sec = settings.rate_limits_seconds.get(interval, 60)
    _limiter = get_limiter(("kline", symbol, interval), _sec)
    async with _limiter:
        data = await http_client.request("GET", url, params=params)
        try:
            prod = IndicatorsProducer(symbol, data, interval)
            await prod.publish()
        except Exception as e:
            logger.error("indicators_producer_error %s %s %s", symbol, interval, e)


async def fetch_topLongShortAccountRatio(symbol: str, period: str):
    """大户账户数多空比"""
    url = BASE_URL + '/futures/data/topLongShortAccountRatio'
    _p = '5m' if period == '1m' else period
    params = {
        'symbol': symbol,
        'period': _p,
        'limit': 30
    }
    _sec = settings.rate_limits_seconds.get(_p, 60)
    _limiter = get_limiter(("topLongShortAccountRatio", symbol, _p), _sec)
    async with _limiter:
        res = await http_client.request("GET", url, params=params)
        try:
            await store_market_raw(symbol, period, url, res)
        except Exception as e:
            logger.error("store_market_raw_error %s %s %s", symbol, period, e)


async def fetch_topLongShortPositionRatio(symbol: str, period: str):
    """大户持仓多空比"""
    url = BASE_URL + '/futures/data/topLongShortPositionRatio'
    _p = '5m' if period == '1m' else period
    params = {
        'symbol': symbol,
        'period': _p,
        'limit': 30
    }
    _sec = settings.rate_limits_seconds.get(_p, 60)
    _limiter = get_limiter(("topLongShortPositionRatio", symbol, _p), _sec)
    async with _limiter:
        res = await http_client.request("GET", url, params=params)
        try:
            await store_market_raw(symbol, period, url, res)
        except Exception as e:
            logger.error("store_market_raw_error %s %s %s", symbol, period, e)


async def fetch_globalLongShortAccountRatio(symbol: str, period: str):
    """全局账户多空比"""
    url = BASE_URL + '/futures/data/globalLongShortAccountRatio'
    _p = '5m' if period == '1m' else period
    params = {
        'symbol': symbol,
        'period': _p,
        'limit': 30
    }
    _sec = settings.rate_limits_seconds.get(_p, 60)
    _limiter = get_limiter(("globalLongShortAccountRatio", symbol, _p), _sec)
    async with _limiter:
        res = await http_client.request("GET", url, params=params)
        try:
            await store_market_raw(symbol, period, url, res)
        except Exception as e:
            logger.error("store_market_raw_error %s %s %s", symbol, period, e)


async def fetch_takerLongShortRatio(symbol: str, period: str):
    """ 合约主动买卖量 """
    url = BASE_URL + '/futures/data/takerlongshortRatio'
    _p = '5m' if period == '1m' else period
    params = {
        'symbol': symbol,
        'period': _p,
        'limit': 30
    }
    _sec = settings.rate_limits_seconds.get(_p, 60)
    _limiter = get_limiter(("takerLongShortRatio", symbol, _p), _sec)
    async with _limiter:
        res = await http_client.request("GET", url, params=params)
        try:
            await store_market_raw(symbol, period, url, res)
        except Exception as e:
            logger.error("store_market_raw_error %s %s %s", symbol, period, e)


async def fetch_openInterestHist(symbol: str, period: str):
    """ 合约持仓量历史 """
    url = BASE_URL + '/futures/data/openInterestHist'
    _p = '5m' if period == '1m' else period
    params = {
        'symbol': symbol,
        'period': _p,
        'limit': 30
    }
    _sec = settings.rate_limits_seconds.get(_p, 60)
    _limiter = get_limiter(("openInterestHist", symbol, _p), _sec)
    async with _limiter:
        res = await http_client.request("GET", url, params=params)
        try:
            await store_market_raw(symbol, period, url, res)
        except Exception as e:
            logger.error("store_market_raw_error %s %s %s", symbol, period, e)


async def fetch_ticker24hr(symbol: str):
    """24h价格变动情况"""
    url = BASE_URL + '/fapi/v1/ticker/24hr'
    params = {
        'symbol': symbol
    }
    _sec = settings.rate_limits_seconds.get('1h', 3600)
    _limiter = get_limiter(("ticker24hr", symbol, '1h'), _sec)
    async with _limiter:
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
        try:
            await store_market_raw_simple(symbol, url, data)
        except Exception as e:
            logger.error("store_market_raw_error %s %s", symbol, e)


async def fetch_fundingRate(symbol: str):
    """获取资金费率"""
    url = BASE_URL + '/fapi/v1/fundingRate'
    params = {
        'symbol': symbol,
        'limit': 200
    }
    _sec = settings.rate_limits_seconds.get('4h', 14400)
    _limiter = get_limiter(("fundingRate", symbol, '4h'), _sec)
    async with _limiter:
        res = await http_client.request("GET", url, params=params)
        try:
            await store_market_raw_simple(symbol, url, res)
        except Exception as e:
            logger.error("store_market_raw_error %s %s", symbol, e)


async def fetch_openInterest(symbol: str):
    """获取未平仓合约数"""
    url = BASE_URL + '/fapi/v1/openInterest'
    params = {
        'symbol': symbol,
        'limit': 200
    }
    _sec = settings.rate_limits_seconds.get('5m', 150)
    _limiter = get_limiter(("fundingRate", symbol, '5m'), _sec)
    async with _limiter:
        res = await http_client.request("GET", url, params=params)
        try:
            await store_market_raw_simple(symbol, url, res)
        except Exception as e:
            logger.error("store_market_raw_error %s %s", symbol, e)


async def spider_poller(symbol: str, interval: str, limit: int = 200):
    while True:
        try:
            await fetch_kline(symbol, interval, limit)
            await fetch_takerLongShortRatio(symbol, interval)
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
            asyncio.create_task(spider_poller("BTCUSDT", "2h", 200)),
            asyncio.create_task(spider_poller("BTCUSDT", "4h", 200)),
            asyncio.create_task(spider_poller("BTCUSDT", "6h", 200)),
            asyncio.create_task(spider_poller("BTCUSDT", "12h", 200)),
            asyncio.create_task(spider_poller("BTCUSDT", "1d", 200)),
            asyncio.create_task(ticker24hr_poller("BTCUSDT")),
            asyncio.create_task(fundingRate_poller("BTCUSDT")),
        ]
        await asyncio.gather(*tasks)
    finally:
        await http_client.close()


if __name__ == "__main__":
    async def _run_once():
        try:
            await fetch_openInterest("BTCUSDT")
        finally:
            await http_client.close()
    # asyncio.run(_main())
    asyncio.run(_run_once())
