import json
from redis.asyncio import Redis
from redis.exceptions import AuthenticationError
try:
    from ..config import settings
except ImportError:
    from agent_server.config import settings


def get_redis_client(db: int | None = None, decode_responses: bool = True) -> Redis:
    host = settings.redis_host
    port = settings.redis_port
    password = settings.redis_password
    use_db = db if db is not None else settings.redis_db
    kwargs = {"host": host, "port": port, "db": use_db, "decode_responses": decode_responses}
    # 兼容 .env 里常见的占位写法（例如 REDIS_PASSWORD=None），避免误触发 AUTH 导致连接失败
    if isinstance(password, str) and password.strip().lower() in ("none", "null", "undefined", ""):
        password = None
    if password:
        kwargs["password"] = password
    return Redis(**kwargs)


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

    async def set_json(self, key: str, value) -> bool:
        data = json.dumps(value, ensure_ascii=False)
        await self.client.set(key, data)
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
