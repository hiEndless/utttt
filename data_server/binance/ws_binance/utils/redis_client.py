import os
import sys
import asyncio
from typing import List, Tuple, Optional, Dict


def build_url():
    host = os.environ.get("REDIS_HOST", "127.0.0.1")
    port = os.environ.get("REDIS_PORT", "6379")
    db = os.environ.get("REDIS_DB", "1")
    password = os.environ.get("REDIS_PASSWORD", None)
    if password:
        return f"redis://:{password}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


# 全局连接池缓存
_ASYNC_CLIENTS = {}
_SYNC_CLIENTS = {}
_SYNC_POOLS = {}  # 缓存连接池，避免重复创建
_ASYNC_BATCH_WRITERS = {}  # 异步批量写入器缓存


def get_async_redis(redis_url=None, decode_responses=True, max_connections=None):
    """
    获取异步 Redis 客户端（单例模式，复用连接池）
    
    Args:
        redis_url: Redis URL（可选）
        decode_responses: 是否自动解码响应
        max_connections: 连接池最大连接数（默认从环境变量读取，或使用 50）
    """
    import redis.asyncio as aioredis
    from redis.asyncio.connection import ConnectionPool
    
    if max_connections is None:
        max_connections = int(os.environ.get("REDIS_MAX_CONNECTIONS", 50))
    
    url = redis_url or build_url()
    cache_key = f"{url}:{decode_responses}:{max_connections}"
    
    client = _ASYNC_CLIENTS.get(cache_key)
    if client is None:
        # 使用 ConnectionPool 确保连接池复用
        # 从 URL 解析连接参数
        pool = aioredis.ConnectionPool.from_url(
            url,
            decode_responses=decode_responses,
            max_connections=max_connections
        )
        client = aioredis.Redis(connection_pool=pool)
        _ASYNC_CLIENTS[cache_key] = client
    return client


def get_sync_redis(host=None, port=None, password=None, db=None, decode_responses=True, max_connections=None):
    """
    获取同步 Redis 客户端（单例模式，复用连接池）
    
    Args:
        host: Redis 主机（可选）
        port: Redis 端口（可选）
        password: Redis 密码（可选）
        db: Redis 数据库编号（可选）
        decode_responses: 是否自动解码响应
        max_connections: 连接池最大连接数（默认从环境变量读取，或使用 50）
    """
    import redis
    
    if max_connections is None:
        max_connections = int(os.environ.get("REDIS_MAX_CONNECTIONS", 50))
    
    h = host or os.environ.get("REDIS_HOST", "127.0.0.1")
    p = int(port or os.environ.get("REDIS_PORT", 6379))
    pw = password or os.environ.get("REDIS_PASSWORD", None)
    d = int(db or os.environ.get("REDIS_DB", 1))
    
    # 使用连接池缓存键
    pool_key = f"{h}:{p}:{d}:{'1' if decode_responses else '0'}:{max_connections}"
    
    # 先检查连接池缓存
    pool = _SYNC_POOLS.get(pool_key)
    if pool is None:
        pool = redis.ConnectionPool(
            host=h, 
            port=p, 
            password=pw, 
            db=d, 
            max_connections=max_connections, 
            decode_responses=decode_responses
        )
        _SYNC_POOLS[pool_key] = pool
    
    # 检查客户端缓存
    client_key = f"{pool_key}:client"
    client = _SYNC_CLIENTS.get(client_key)
    if client is None:
        client = redis.Redis(connection_pool=pool)
        _SYNC_CLIENTS[client_key] = client
    
    return client


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


def key_force_stats_stream(symbol: str):
    return f"force_stats_stream:binance:{symbol}"


def key_ticks(symbol: str):
    return f"ticks:binance:{symbol}"


def key_latest_price(symbol: str):
    return f"price:binance:{symbol}"


def key_alerts(symbol: str):
    return f"alerts:binance:{symbol}"


class AsyncRedisBatchWriter:
    """
    异步 Redis 批量写入器，支持海量数据瞬时插入
    
    使用 pipeline 批量执行写入操作，减少网络往返次数。
    支持自动刷新和手动刷新。
    """
    
    def __init__(self, redis_client, batch_size: int = 100, flush_interval: float = 0.1):
        """
        Args:
            redis_client: 异步 Redis 客户端对象
            batch_size: 批量写入大小，达到此数量时自动刷新
            flush_interval: 自动刷新间隔（秒），即使未达到 batch_size 也会刷新
        """
        self.redis_client = redis_client
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._pending_ops: List[Tuple[str, tuple, dict]] = []  # (method, args, kwargs)
        self._last_flush_time = 0.0
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
    
    async def _flush(self):
        """刷新 pipeline，执行所有待处理的操作"""
        if not self._pending_ops:
            return
        
        pipeline = self.redis_client.pipeline()
        for method_name, args, kwargs in self._pending_ops:
            method = getattr(pipeline, method_name)
            method(*args, **kwargs)
        
        try:
            await pipeline.execute()
        except Exception as e:
            # 记录错误但不抛出，避免影响其他操作
            print(f"redis_async_batch_write_error: {e}")
        finally:
            self._pending_ops.clear()
            self._last_flush_time = asyncio.get_event_loop().time()
    
    async def _auto_flush_check(self):
        """检查是否需要自动刷新"""
        current_time = asyncio.get_event_loop().time()
        should_flush = (
            len(self._pending_ops) >= self.batch_size or
            (self._pending_ops and current_time - self._last_flush_time >= self.flush_interval)
        )
        if should_flush:
            await self._flush()
    
    async def xadd(self, key: str, fields: dict, *args, **kwargs):
        """批量 XADD 操作"""
        async with self._lock:
            # 确保所有值都是字符串
            str_fields = {k: str(v) for k, v in fields.items()}
            self._pending_ops.append(("xadd", (key, str_fields) + args, kwargs))
            await self._auto_flush_check()
    
    async def hset(self, key: str, mapping: dict = None, **kwargs):
        """批量 HSET 操作"""
        async with self._lock:
            if mapping is not None:
                # 确保所有值都是字符串
                str_mapping = {k: str(v) for k, v in mapping.items()}
                self._pending_ops.append(("hset", (key,), {"mapping": str_mapping, **kwargs}))
            else:
                str_kwargs = {k: str(v) for k, v in kwargs.items()}
                self._pending_ops.append(("hset", (key,), str_kwargs))
            await self._auto_flush_check()
    
    async def flush(self):
        """手动刷新，立即执行所有待处理的操作"""
        async with self._lock:
            await self._flush()
    
    async def close(self):
        """关闭批量写入器，刷新所有待处理的操作"""
        async with self._lock:
            await self._flush()
            if self._flush_task:
                self._flush_task.cancel()
                try:
                    await self._flush_task
                except asyncio.CancelledError:
                    pass


def get_async_batch_writer(redis_client, batch_size: int = None, flush_interval: float = None) -> AsyncRedisBatchWriter:
    """
    获取异步批量写入器（单例模式）
    
    每个 Redis 客户端对象共享一个批量写入器。
    """
    if batch_size is None:
        batch_size = int(os.environ.get("REDIS_BATCH_SIZE", 100))
    if flush_interval is None:
        flush_interval = float(os.environ.get("REDIS_FLUSH_INTERVAL", 0.1))
    
    # 使用客户端对象的 id 作为缓存键
    cache_key = id(redis_client)
    
    if cache_key not in _ASYNC_BATCH_WRITERS:
        _ASYNC_BATCH_WRITERS[cache_key] = AsyncRedisBatchWriter(
            redis_client=redis_client,
            batch_size=batch_size,
            flush_interval=flush_interval
        )
    
    return _ASYNC_BATCH_WRITERS[cache_key]

