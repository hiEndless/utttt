import json
import asyncio
import os
import sys
import weakref
from typing import Optional, Dict, List, Tuple
from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool
from redis.asyncio.client import Pipeline
try:
    from config import settings
except ImportError:
    from ..config import settings

# 全局连接池缓存：按 (host, port, db, decode_responses) 缓存连接池
_POOLS_BY_LOOP: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[tuple, ConnectionPool]]" = weakref.WeakKeyDictionary(
)
_POOLS_NO_LOOP: dict[tuple, ConnectionPool] = {}
_POOLS_LOCK = asyncio.Lock()


def _redis_max_connections(default: int = 50) -> int:
    """获取 Redis 连接池最大连接数，默认 50（可根据并发任务数调整）"""
    try:
        # 优先使用配置中的值
        if hasattr(settings, 'redis_max_connections'):
            return settings.redis_max_connections
        return int(os.environ.get("REDIS_MAX_CONNECTIONS", default))
    except Exception:
        return default


def _redis_socket_keepalive() -> bool:
    """是否启用 socket keepalive，默认 True"""
    try:
        return os.environ.get("REDIS_SOCKET_KEEPALIVE",
                              "true").lower() == "true"
    except Exception:
        return True


def get_redis_client(db: int | None = None,
                     decode_responses: bool = True) -> Redis:
    """
    获取 Redis 客户端（单例模式，复用连接池）
    
    每个 (host, port, db, decode_responses) 组合共享一个连接池，
    避免在高并发场景下创建过多连接。
    """
    host = settings.redis_host
    port = settings.redis_port
    password = settings.redis_password
    use_db = db if db is not None else settings.redis_db
    pool_key = (host, port, use_db, bool(decode_responses))

    # 尝试从缓存获取连接池
    try:
        loop = asyncio.get_running_loop()
        loop_pools = _POOLS_BY_LOOP.get(loop)
        if loop_pools is not None and pool_key in loop_pools:
            pool = loop_pools[pool_key]
            if pool.is_connected:
                return Redis(connection_pool=pool)
    except RuntimeError:
        if pool_key in _POOLS_NO_LOOP:
            pool = _POOLS_NO_LOOP[pool_key]
            if pool.is_connected:
                return Redis(connection_pool=pool)

    # 创建新的连接池
    max_conn = _redis_max_connections()
    pool_kwargs = {
        "host": host,
        "port": port,
        "db": use_db,
        "decode_responses": decode_responses,
        "max_connections": max_conn,
    }
    
    # Socket keepalive 配置
    # 注意：Windows 平台可能不支持 socket_keepalive_options，只启用基本的 keepalive
    if _redis_socket_keepalive():
        pool_kwargs["socket_keepalive"] = True
        # Windows 平台不支持 socket_keepalive_options，跳过以避免错误
        if sys.platform != 'win32':
            try:
                import socket
                keepalive_opts = {}
                if hasattr(socket, 'TCP_KEEPIDLE'):
                    keepalive_opts[socket.TCP_KEEPIDLE] = 1
                if hasattr(socket, 'TCP_KEEPINTVL'):
                    keepalive_opts[socket.TCP_KEEPINTVL] = 3
                if hasattr(socket, 'TCP_KEEPCNT'):
                    keepalive_opts[socket.TCP_KEEPCNT] = 5
                if keepalive_opts:
                    pool_kwargs["socket_keepalive_options"] = keepalive_opts
            except Exception:
                # 如果获取选项失败，只使用基本的 keepalive
                pass
    
    if password:
        pool_kwargs["password"] = password

    pool = ConnectionPool(**pool_kwargs)

    # 缓存连接池
    try:
        loop = asyncio.get_running_loop()
        loop_pools = _POOLS_BY_LOOP.get(loop)
        if loop_pools is None:
            loop_pools = {}
            _POOLS_BY_LOOP[loop] = loop_pools
        loop_pools[pool_key] = pool
    except RuntimeError:
        _POOLS_NO_LOOP[pool_key] = pool

    return Redis(connection_pool=pool)


class RedisBatchWriter:
    """
    Redis 批量写入器，支持海量数据瞬时插入
    
    使用 pipeline 批量执行写入操作，减少网络往返次数。
    支持自动刷新和手动刷新。
    """

    def __init__(self,
                 db: int | None = None,
                 decode_responses: bool = True,
                 batch_size: int = 100,
                 flush_interval: float = 0.1):
        """
        Args:
            db: Redis 数据库编号
            decode_responses: 是否自动解码响应
            batch_size: 批量写入大小，达到此数量时自动刷新
            flush_interval: 自动刷新间隔（秒），即使未达到 batch_size 也会刷新
        """
        self.client = get_redis_client(db, decode_responses)
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._pipeline: Optional[Pipeline] = None
        self._pending_ops: List[Tuple[str, tuple,
                                      dict]] = []  # (method, args, kwargs)
        self._last_flush_time = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None

    def _get_pipeline(self) -> Pipeline:
        """获取 pipeline 对象"""
        if self._pipeline is None:
            self._pipeline = self.client.pipeline()
        return self._pipeline

    async def _flush(self):
        """刷新 pipeline，执行所有待处理的操作"""
        if not self._pending_ops:
            return

        pipeline = self._get_pipeline()
        for method_name, args, kwargs in self._pending_ops:
            method = getattr(pipeline, method_name)
            method(*args, **kwargs)

        try:
            await pipeline.execute()
        except Exception as e:
            # 记录错误但不抛出，避免影响其他操作
            import logging
            logging.error("redis_batch_write_error %s", e)
        finally:
            self._pending_ops.clear()
            self._pipeline = None
            self._last_flush_time = asyncio.get_event_loop().time()

    async def _auto_flush_check(self):
        """检查是否需要自动刷新"""
        current_time = asyncio.get_event_loop().time()
        should_flush = (len(self._pending_ops) >= self.batch_size
                        or (self._pending_ops and current_time -
                            self._last_flush_time >= self.flush_interval))
        if should_flush:
            await self._flush()

    async def set(self, key: str, value: str, *args, **kwargs):
        """批量 SET 操作"""
        async with self._lock:
            self._pending_ops.append(("set", (key, value) + args, kwargs))
            await self._auto_flush_check()

    async def set_json(self, key: str, value, *args, **kwargs):
        """批量 SET JSON 操作"""
        data = json.dumps(value, ensure_ascii=False)
        await self.set(key, data, *args, **kwargs)

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


# 全局批量写入器缓存（按 db 和 decode_responses 缓存）
_BATCH_WRITERS: Dict[Tuple[int, bool], RedisBatchWriter] = {}


def get_batch_writer(db: int | None = None,
                     decode_responses: bool = True,
                     batch_size: int = None,
                     flush_interval: float = None) -> RedisBatchWriter:
    """
    获取批量写入器（单例模式）
    
    每个 (db, decode_responses) 组合共享一个批量写入器。
    
    Args:
        db: Redis 数据库编号
        decode_responses: 是否自动解码响应
        batch_size: 批量写入大小，默认使用配置值
        flush_interval: 批量写入刷新间隔，默认使用配置值
    """
    use_db = db if db is not None else settings.redis_db
    cache_key = (use_db, bool(decode_responses))

    if cache_key not in _BATCH_WRITERS:
        # 使用配置中的默认值
        if batch_size is None:
            batch_size = getattr(settings, 'redis_batch_size', 100)
        if flush_interval is None:
            flush_interval = getattr(settings, 'redis_flush_interval', 0.1)

        _BATCH_WRITERS[cache_key] = RedisBatchWriter(
            db=use_db,
            decode_responses=decode_responses,
            batch_size=batch_size,
            flush_interval=flush_interval)

    return _BATCH_WRITERS[cache_key]


class RedisClient:

    def __init__(self, db: int | None = None, decode_responses: bool = True):
        self.client = get_redis_client(db, decode_responses)

    async def set_json(self, key: str, value) -> bool:
        data = json.dumps(value, ensure_ascii=False)
        await self.client.set(key, data)
        return True

    async def get(self, key: str):
        return await self.client.get(key)
