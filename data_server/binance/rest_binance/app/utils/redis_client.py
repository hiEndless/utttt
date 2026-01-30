import json
from redis.asyncio import Redis
try:
    from config import settings
except ImportError:
    from ..config import settings


# 连接池缓存（避免Too many connections错误）
_CONNECTION_POOLS = {}

def get_redis_client(db: int | None = None, decode_responses: bool = True, max_connections: int = 100) -> Redis:
    """
    获取Redis客户端（使用连接池，优化连接数）
    
    Args:
        db: Redis数据库编号
        decode_responses: 是否自动解码响应
        max_connections: 最大连接数（默认100，避免Too many connections错误）
    
    Returns:
        Redis客户端实例
    """
    from redis.asyncio import ConnectionPool
    
    host = settings.redis_host
    port = settings.redis_port
    password = settings.redis_password
    use_db = db if db is not None else settings.redis_db
    
    # 使用缓存键来复用连接池
    pool_key = f"{host}:{port}:{use_db}:{decode_responses}:{max_connections}"
    
    if pool_key not in _CONNECTION_POOLS:
        pool_kwargs = {
            "host": host,
            "port": port,
            "db": use_db,
            "decode_responses": decode_responses,
            "max_connections": max_connections,
            "retry_on_timeout": True,
            "socket_keepalive": True,
            "socket_keepalive_options": {},
            "health_check_interval": 30
        }
        if password:
            pool_kwargs["password"] = password
        
        pool = ConnectionPool(**pool_kwargs)
        _CONNECTION_POOLS[pool_key] = pool
    
    return Redis(connection_pool=_CONNECTION_POOLS[pool_key])


class RedisClient:
    def __init__(self, db: int | None = None, decode_responses: bool = True):
        self.client = get_redis_client(db, decode_responses)

    async def set_json(self, key: str, value) -> bool:
        data = json.dumps(value, ensure_ascii=False)
        await self.client.set(key, data)
        return True

    async def get(self, key: str):
        return await self.client.get(key)