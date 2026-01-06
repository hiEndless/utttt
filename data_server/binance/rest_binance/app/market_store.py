import json
from utils.redis_client import get_redis_client


def extract_endpoint_name(url: str) -> str:
    name = (url or "").rstrip("/").split("/")[-1]
    if name == "takerlongshortRatio":
        return "takerLongShortRatio"
    return name


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

async def delete_market_raw_all(db: int | None = None, count: int = 1000, dry_run: bool = False) -> dict:
    client = get_redis_client(db)
    cursor = 0
    matched = 0
    deleted = 0
    while True:
        cursor, keys = await client.scan(cursor=cursor, match="market_raw:*", count=count)
        matched += len(keys)
        if not dry_run and keys:
            deleted += await client.delete(*keys)
        if cursor == 0:
            break
    return {"matched": matched, "deleted": deleted, "dry_run": dry_run}

if __name__ == "__main__":
    import asyncio
    asyncio.run(delete_market_raw_all())