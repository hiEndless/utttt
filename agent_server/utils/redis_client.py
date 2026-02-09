import json
import asyncio
import os
import weakref
from redis.asyncio import Redis
from redis.exceptions import AuthenticationError
try:
    from ..config import settings
except ImportError:
    from agent_server.config import settings


# 中文注释：redis-py asyncio 客户端/连接池会绑定到事件循环；这里按事件循环缓存，避免高频 new 客户端导致连接数暴涨
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
        # 中文注释：显式限制连接池上限，避免默认值过大导致 Redis maxclients 被打满
        "max_connections": _redis_max_connections(),
    }
    # 兼容 .env 里常见的占位写法（例如 REDIS_PASSWORD=None），避免误触发 AUTH 导致连接失败
    if isinstance(password, str) and password.strip().lower() in ("none", "null", "undefined", ""):
        password = None
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


async def get_verified_redis_client(db: int | None = None, decode_responses: bool = True) -> Redis:
    """
    获取可用的 Redis 客户端：
    - 若服务端未配置密码但环境变量误带了密码，会触发 AUTH 报错；此处自动降级为无密码连接，避免脚本直跑失败
    """
    client = get_redis_client(db=db, decode_responses=decode_responses)
    try:
        await client.ping()
        return client
    except AuthenticationError as e:
        msg = str(e)
        if "called without any password configured" not in msg:
            raise
        try:
            if hasattr(client, "aclose"):
                await client.aclose()
            else:
                await client.close()
        except Exception:
            pass
        kwargs = {
            "host": settings.redis_host,
            "port": settings.redis_port,
            "db": db if db is not None else settings.redis_db,
            "decode_responses": decode_responses,
        }
        client2 = Redis(**kwargs)
        await client2.ping()
        return client2


class RedisClient:
    def __init__(self, db: int | None = None, decode_responses: bool = True):
        self.client = get_redis_client(db, decode_responses)

    async def set_json(self, key: str, value, ex: int | None = None) -> bool:
        # 中文注释：统一 JSON 落库入口；必要时可通过 ex 设置 Redis TTL（秒）
        data = json.dumps(value, ensure_ascii=False)
        await self.client.set(key, data, ex=ex)
        return True

    async def get(self, key: str):
        return await self.client.get(key)

    async def xadd_json(self, key: str, payload: dict, ts: int | None = None, maxlen: int | None = None, approximate: bool = True) -> str:
        fields = {"payload": json.dumps(payload, ensure_ascii=False)}
        if ts is not None:
            fields["ts"] = int(ts)
        return await self.client.xadd(key, fields, maxlen=maxlen, approximate=approximate)

    async def xrevrange_latest(self, key: str):
        try:
            res = await self.client.xrevrange(key, max="+", min="-", count=1)
            if not res:
                return None
            _, fields = res[0]
            payload = fields.get("payload")
            if isinstance(payload, str):
                try:
                    return json.loads(payload)
                except Exception:
                    return None
            return None
        except Exception:
            return None
