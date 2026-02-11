import json
try:
    from config import settings
except ImportError:
    from ..config import settings
from utils.redis_client import get_redis_client, get_batch_writer


def extract_endpoint_name(url: str) -> str:
    name = (url or "").rstrip("/").split("/")[-1]
    if name == "takerlongshortRatio":
        return "takerLongShortRatio"
    return name


async def store_market_raw(symbol: str, interval: str, url: str, data, db: int | None = None, exchange: str = "binance", use_batch: bool = True):
    """
    存储市场原始数据
    
    Args:
        symbol: 交易对符号
        interval: 时间周期
        url: API 端点 URL
        data: 数据内容
        db: Redis 数据库编号
        exchange: 交易所名称
        use_batch: 是否使用批量写入（默认 True，提高性能）
    """
    name = extract_endpoint_name(url)
    key = f"market_raw:{exchange}:{symbol}:{interval}:{name}"
    json_data = json.dumps(data, ensure_ascii=False)
    
    if use_batch:
        # 使用批量写入器，支持海量数据瞬时插入
        writer = get_batch_writer(db=db)
        await writer.set(key, json_data)
    else:
        # 直接写入（用于需要立即生效的场景）
        client = get_redis_client(db)
        await client.set(key, json_data)
    return True


async def store_market_raw_simple(symbol: str, url: str, data, db: int | None = None, exchange: str = "binance", use_batch: bool = True):
    """
    存储市场原始数据（简化版，无 interval）
    
    Args:
        symbol: 交易对符号
        url: API 端点 URL
        data: 数据内容
        db: Redis 数据库编号
        exchange: 交易所名称
        use_batch: 是否使用批量写入（默认 True，提高性能）
    """
    name = extract_endpoint_name(url)
    key = f"market_raw:{exchange}:{symbol}:{name}"
    json_data = json.dumps(data, ensure_ascii=False)
    
    if use_batch:
        # 使用批量写入器，支持海量数据瞬时插入
        writer = get_batch_writer(db=db)
        await writer.set(key, json_data)
    else:
        # 直接写入（用于需要立即生效的场景）
        client = get_redis_client(db)
        await client.set(key, json_data)
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