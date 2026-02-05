import json
import asyncio
import os
import weakref
from redis.asyncio import Redis
try:
    from config import settings
except ImportError:
    from ..config import settings


# 中文注释：高频写入场景复用 Redis 客户端，避免每次调用都新建连接池导致连接数暴涨
_CLIENTS_BY_LOOP: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[tuple[int, bool], Redis]]" = weakref.WeakKeyDictionary()
_CLIENTS_NO_LOOP: dict[tuple[int, bool], Redis] = {}


def _redis_max_connections(default: int = 20) -> int:
    try:
        return int(os.environ.get("REDIS_MAX_CONNECTIONS", default))
    except Exception:
        return default


def get_redis_client(db: int | None = None, decode_responses: bool = True) -> Redis:
    host = settings.redis_host
    port = settings.redis_port
    password = settings.redis_password
    use_db = db if db is not None else settings.redis_db
    cache_key = (use_db, bool(decode_responses))
    try:
        loop = asyncio.get_running_loop()
        loop_cache = _CLIENTS_BY_LOOP.get(loop)
        if loop_cache is not None and cache_key in loop_cache:
            return loop_cache[cache_key]
    except RuntimeError:
        if cache_key in _CLIENTS_NO_LOOP:
            return _CLIENTS_NO_LOOP[cache_key]

    kwargs = {
        "host": host,
        "port": port,
        "db": use_db,
        "decode_responses": decode_responses,
        # 中文注释：限制连接池最大连接数，避免 Redis 端报 Too many connections
        "max_connections": _redis_max_connections(),
    }
    if password:
        kwargs["password"] = password
    client = Redis(**kwargs)
    try:
        loop = asyncio.get_running_loop()
        loop_cache = _CLIENTS_BY_LOOP.get(loop)
        if loop_cache is None:
            loop_cache = {}
            _CLIENTS_BY_LOOP[loop] = loop_cache
        loop_cache[cache_key] = client
    except RuntimeError:
        _CLIENTS_NO_LOOP[cache_key] = client
    return client


class RedisClient:
    def __init__(self, db: int | None = None, decode_responses: bool = True):
        self.client = get_redis_client(db, decode_responses)

    async def set_json(self, key: str, value) -> bool:
        data = json.dumps(value, ensure_ascii=False)
        await self.client.set(key, data)
        return True

    async def get(self, key: str):
        return await self.client.get(key)
