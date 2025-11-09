from redis.asyncio import Redis, ConnectionPool
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# Redis连接配置
REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
REDIS_PORT = os.getenv('REDIS_PORT', 6379)
REDIS_DB = os.getenv('REDIS_DB', 3)
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
    'max_connections': 10  # 最大连接数
}

# 只有当密码不为None时才添加password参数
if REDIS_HOST == '127.0.0.1':
    pool_kwargs.pop('password')

_redis_pool = ConnectionPool(**pool_kwargs)

# 创建Redis客户端实例
redis_client = Redis(connection_pool=_redis_pool)