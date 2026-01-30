import os


def build_url():
    host = os.environ.get("REDIS_HOST", "127.0.0.1")
    port = os.environ.get("REDIS_PORT", "6379")
    db = os.environ.get("REDIS_DB", "1")
    password = os.environ.get("REDIS_PASSWORD", None)
    if password:
        return f"redis://:{password}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


_ASYNC_CLIENTS = {}
_SYNC_CLIENTS = {}


def get_async_redis(redis_url=None, decode_responses=True, max_connections=100):
    """
    获取异步Redis客户端（使用连接池，优化连接数）
    
    Args:
        redis_url: Redis URL（可选）
        decode_responses: 是否自动解码响应
        max_connections: 最大连接数（默认100，避免Too many connections错误）
    """
    import redis.asyncio as aioredis
    url = redis_url or build_url()
    cache_key = f"{url}:{decode_responses}:{max_connections}"
    client = _ASYNC_CLIENTS.get(cache_key)
    if client is None:
        client = aioredis.from_url(
            url, 
            decode_responses=decode_responses, 
            max_connections=max_connections,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={}
        )
        _ASYNC_CLIENTS[cache_key] = client
    return client


def get_sync_redis(host=None, port=None, password=None, db=None, decode_responses=True, max_connections=100):
    """
    获取同步Redis客户端（使用连接池，优化连接数）
    
    Args:
        host: Redis主机
        port: Redis端口
        password: Redis密码
        db: Redis数据库
        decode_responses: 是否自动解码响应
        max_connections: 最大连接数（默认100，避免Too many connections错误）
    """
    import redis
    h = host or os.environ.get("REDIS_HOST", "127.0.0.1")
    p = int(port or os.environ.get("REDIS_PORT", 6379))
    pw = password or os.environ.get("REDIS_PASSWORD", None)
    d = int(db or os.environ.get("REDIS_DB", 1))
    key = f"{h}:{p}:{d}:{'1' if decode_responses else '0'}:{max_connections}"
    client = _SYNC_CLIENTS.get(key)
    if client is None:
        pool = redis.ConnectionPool(
            host=h, 
            port=p, 
            password=pw, 
            db=d, 
            max_connections=max_connections, 
            decode_responses=decode_responses,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={},
            health_check_interval=30  # 健康检查间隔
        )
        client = redis.Redis(connection_pool=pool)
        _SYNC_CLIENTS[key] = client
    return client


async def safe_hset_async(client, key: str, mapping: dict):
    """
    安全的异步HSET操作（带重试机制，避免Too many connections错误）
    """
    import asyncio
    max_retries = 3
    retry_delay = 0.1  # 100ms
    
    for attempt in range(max_retries):
        try:
            ktype = await client.type(key)
            if ktype and ktype != "hash" and ktype != "none":
                await client.delete(key)
            await client.hset(key, mapping=mapping)
            return  # 成功则返回
        except Exception as e:
            error_str = str(e)
            # 如果是连接错误，重试
            if ("Too many connections" in error_str or "Connection" in error_str) and attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))  # 指数退避
                continue
            # 其他错误或重试失败，记录
            if attempt == max_retries - 1:  # 最后一次重试失败才记录
                try:
                    ktype = await client.type(key)
                except Exception:
                    ktype = "unknown"
                print(f"Redis HSET error on key={key} type={ktype}: {e} (retried {max_retries} times)")
            return


def safe_hset_sync(client, key: str, mapping: dict):
    """
    安全的HSET操作（带重试机制，避免Too many connections错误）
    """
    import time
    max_retries = 3
    retry_delay = 0.1  # 100ms
    
    for attempt in range(max_retries):
        try:
            ktype = client.type(key)
            if ktype and ktype != "hash" and ktype != "none":
                client.delete(key)
            client.hset(key, mapping=mapping)
            return  # 成功则返回
        except Exception as e:
            error_str = str(e)
            # 如果是连接错误，重试
            if ("Too many connections" in error_str or "Connection" in error_str) and attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # 指数退避
                continue
            # 其他错误或重试失败，记录
            if attempt == max_retries - 1:  # 最后一次重试失败才记录
                try:
                    ktype = client.type(key)
                except Exception:
                    ktype = "unknown"
                print(f"Redis HSET error on key={key} type={ktype}: {e} (retried {max_retries} times)")
            return


async def safe_xadd_async(client, key: str, fields: dict, maxlen=None, approximate=True):
    """
    安全的异步XADD操作（带重试机制，避免Too many connections错误）
    """
    import asyncio
    max_retries = 3
    retry_delay = 0.1  # 100ms
    
    for attempt in range(max_retries):
        try:
            await client.xadd(key, fields, maxlen=maxlen, approximate=approximate)
            return  # 成功则返回
        except Exception as e:
            error_str = str(e)
            # 如果是连接错误，重试
            if ("Too many connections" in error_str or "Connection" in error_str) and attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))  # 指数退避
                continue
            # 其他错误或重试失败，记录
            if attempt == max_retries - 1:  # 最后一次重试失败才记录
                try:
                    ktype = await client.type(key)
                except Exception:
                    ktype = "unknown"
                print(f"Redis XADD error on key={key} type={ktype}: {e} (retried {max_retries} times)")
            return


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


def key_force_stats_stream(symbol: str):
    return f"force_stats_stream:binance:{symbol}"


def key_ticks(symbol: str):
    return f"ticks:binance:{symbol}"


def key_latest_price(symbol: str):
    return f"price:binance:{symbol}"


def key_alerts(symbol: str):
    return f"alerts:binance:{symbol}"

