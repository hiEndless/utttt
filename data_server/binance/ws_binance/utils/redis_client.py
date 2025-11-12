import os


def build_url():
    host = os.environ.get("REDIS_HOST", "127.0.0.1")
    port = os.environ.get("REDIS_PORT", "6379")
    db = os.environ.get("REDIS_DB", "1")
    password = os.environ.get("REDIS_PASSWORD", None)
    if password:
        return f"redis://:{password}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


def get_async_redis(redis_url=None, decode_responses=True):
    import redis.asyncio as aioredis
    url = redis_url or build_url()
    return aioredis.from_url(url, decode_responses=decode_responses)


def get_sync_redis(host=None, port=None, password=None, db=None, decode_responses=True):
    import redis
    h = host or os.environ.get("REDIS_HOST", "127.0.0.1")
    p = int(port or os.environ.get("REDIS_PORT", 6379))
    pw = password or os.environ.get("REDIS_PASSWORD", None)
    d = int(db or os.environ.get("REDIS_DB", 1))
    return redis.Redis(host=h, port=p, password=pw, db=d, decode_responses=decode_responses)


async def safe_hset_async(client, key: str, mapping: dict):
    try:
        ktype = await client.type(key)
        if ktype and ktype != "hash" and ktype != "none":
            await client.delete(key)
        await client.hset(key, mapping=mapping)
    except Exception as e:
        try:
            ktype = await client.type(key)
        except Exception:
            ktype = "unknown"
        print(f"Redis HSET error on key={key} type={ktype}: {e}")


def safe_hset_sync(client, key: str, mapping: dict):
    try:
        ktype = client.type(key)
        if ktype and ktype != "hash" and ktype != "none":
            client.delete(key)
        client.hset(key, mapping=mapping)
    except Exception as e:
        try:
            ktype = client.type(key)
        except Exception:
            ktype = "unknown"
        print(f"Redis HSET error on key={key} type={ktype}: {e}")


async def safe_xadd_async(client, key: str, fields: dict, maxlen=None, approximate=True):
    try:
        await client.xadd(key, fields, maxlen=maxlen, approximate=approximate)
    except Exception as e:
        try:
            ktype = await client.type(key)
        except Exception:
            ktype = "unknown"
        print(f"Redis XADD error on key={key} type={ktype}: {e}")


def safe_xadd_sync(client, key: str, fields: dict, maxlen=None, approximate=True):
    try:
        client.xadd(key, fields, maxlen=maxlen, approximate=approximate)
    except Exception as e:
        try:
            ktype = client.type(key)
        except Exception:
            ktype = "unknown"
        print(f"Redis XADD error on key={key} type={ktype}: {e}")


def key_force_stream(symbol: str):
    return f"force_stream:binance:{symbol}"


def key_force_stats(symbol: str):
    return f"force_stats:binance:{symbol}"


def key_ticks(symbol: str):
    return f"ticks:binance:{symbol}"


def key_latest_price(symbol: str):
    return f"price:binance:{symbol}"


def key_alerts(symbol: str):
    return f"alerts:binance:{symbol}"

