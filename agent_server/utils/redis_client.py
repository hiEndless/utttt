import json
from redis.asyncio import Redis
try:
    from ..config import settings
except ImportError:
    from config import settings


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
