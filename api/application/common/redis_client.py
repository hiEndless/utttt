from redis.asyncio import Redis, ConnectionPool
import asyncio
import os
import weakref
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# Redis连接配置
REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
REDIS_PORT = os.getenv('REDIS_PORT', 6379)
REDIS_DB = os.getenv('REDIS_DB', 1)
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

# 创建Redis连接池
# 只有当密码不为None时才在连接池中使用密码参数
pool_kwargs = {
    'host': REDIS_HOST,
    'port': REDIS_PORT,
    'db': REDIS_DB,
    'password': REDIS_PASSWORD,
    'decode_responses': True,  # 自动解码响应
    'encoding': 'utf-8',
    # 中文注释：限制连接池最大连接数，避免 Redis 端 maxclients 被打满（可用环境变量覆盖）
    'max_connections': int(os.getenv('REDIS_MAX_CONNECTIONS', 5))
}

# 只有当密码不为None时才添加password参数
if REDIS_HOST == '127.0.0.1':
    pool_kwargs.pop('password')

_redis_pool = ConnectionPool(**pool_kwargs)

# 创建Redis客户端实例
redis_client = Redis(connection_pool=_redis_pool)

# 注意：redis-py 的 asyncio 连接会绑定到创建/使用它的事件循环。
# 如果在同一进程内多次 asyncio.run（每次都会创建并关闭一个新的事件循环），复用全局连接池可能触发
# “Future attached to a different loop / Event loop is closed”。
# 这里提供一个按事件循环隔离的 client 获取方法，避免跨 loop 复用连接。
_clients_by_loop: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, Redis]" = weakref.WeakKeyDictionary()


def get_async_redis_client() -> Redis:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return redis_client
    cli = _clients_by_loop.get(loop)
    if cli is None:
        pool = ConnectionPool(**pool_kwargs)
        cli = Redis(connection_pool=pool)
        _clients_by_loop[loop] = cli
    return cli
