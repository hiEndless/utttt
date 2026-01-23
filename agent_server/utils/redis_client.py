import json
from redis.asyncio import Redis
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
    if password:
        kwargs["password"] = password
    return Redis(**kwargs)


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
