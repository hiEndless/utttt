import json

try:
    from .redis_client import get_redis_client
except ImportError:
    from redis_client import get_redis_client


def extract_endpoint_name(url: str) -> str:
    return (url or "").rstrip("/").split("/")[-1]


async def store_market_raw(symbol: str, interval: str, url: str, data, db: int | None = None, exchange: str = "binance"):
    client = get_redis_client(db)
    name = extract_endpoint_name(url)
    key = f"market_raw:{exchange}:{symbol}:{interval}:{name}"
    await client.set(key, json.dumps(data, ensure_ascii=False))
    return True


async def store_market_raw_simple(symbol: str, url: str, data, db: int | None = None, exchange: str = "binance"):
    client = get_redis_client(db)
    name = extract_endpoint_name(url)
    key = f"market_raw:{exchange}:{symbol}:{name}"
    await client.set(key, json.dumps(data, ensure_ascii=False))
    return True