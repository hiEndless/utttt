"""
Redis 推送交易 JSON 工具
- 推送到 TASK_ADD_TRADE 队列
- 订单 ID 去重（trading:orders:{exchange}）
- 交易对去重（trading:open_positions:{exchange}）
"""
import json
import time
import hashlib
import logging
from typing import Dict, Optional

try:
    import redis
except ImportError:
    redis = None

logger = logging.getLogger("trade_push")

TRADE_QUEUE_NAME = "TASK_ADD_TRADE"


def _get_trade_redis_config() -> dict:
    """从 settings 获取交易 Redis 配置"""
    from agent_server.config import settings
    host = getattr(settings, "trade_redis_host", None) or settings.redis_host
    password = getattr(settings, "trade_redis_password", None)
    if password is None:
        password = settings.redis_password
    if isinstance(password, str) and password.strip().lower() in ("none", "null", "", "undefined"):
        password = None
    return {
        "host": host,
        "port": getattr(settings, "trade_redis_port", 6379),
        "password": password,
        "db": getattr(settings, "trade_redis_db", 8),
        "decode_responses": False,
    }


async def push_trade_to_redis(
    trade_json: Dict,
    queue_name: str = TRADE_QUEUE_NAME,
    redis_config: Optional[dict] = None,
    redis_client=None,
) -> bool:
    """
    推送交易订单到 Redis 队列（含去重）

    Args:
        trade_json: 交易 JSON，需含 symbol, order_type
        queue_name: Redis 队列名
        redis_config: 交易 Redis 配置，None 则从 settings 获取
        redis_client: 用于去重检查的 RedisClient，None 则新建

    Returns:
        True 推送成功，False 跳过或失败
    """
    if not redis:
        logger.error("redis 模块未安装，无法推送交易")
        return False
    try:
        symbol = trade_json.get("symbol", "")
        order_type = trade_json.get("order_type", "open")
        exchange = trade_json.get("exchange", "binance")

        timestamp = int(time.time() * 1000)
        trade_str = json.dumps(trade_json, sort_keys=True, ensure_ascii=False)
        trade_hash = hashlib.md5(trade_str.encode()).hexdigest()[:8]
        order_id = f"{symbol}_{timestamp}_{order_type}_{trade_hash}"

        if redis_client is None:
            from agent_server.utils.redis_client import RedisClient
            redis_client = RedisClient()
        rc = redis_client.client if hasattr(redis_client, "client") else redis_client

        order_key = f"trading:orders:{exchange}"
        position_key = f"trading:open_positions:{exchange}"

        if await rc.sismember(order_key, order_id):
            logger.warning(f"订单已存在，跳过: {order_id} | {symbol}")
            return False

        if order_type == "open":
            if await rc.sismember(position_key, symbol):
                logger.warning(f"交易对已开仓，跳过: {symbol}")
                return False

        cfg = redis_config or _get_trade_redis_config()
        password = cfg.get("password")
        if isinstance(password, str) and str(password).strip().lower() in ("none", "null", ""):
            password = None

        r = redis.Redis(
            host=cfg["host"],
            port=cfg["port"],
            password=password,
            db=cfg["db"],
            decode_responses=cfg.get("decode_responses", False),
            socket_connect_timeout=10,
            socket_timeout=10,
        )
        json_str = json.dumps(trade_json, ensure_ascii=False)
        result = r.lpush(queue_name, json_str)
        r.close()

        if result:
            await rc.sadd(order_key, order_id)
            if order_type == "open":
                await rc.sadd(position_key, symbol)
            elif order_type == "close":
                await rc.srem(position_key, symbol)
            logger.info(f"订单已推送: {order_id} | {symbol}")
            logger.info(f"[推送记录] trade_json={json_str}")
            return True
        return False
    except Exception as e:
        logger.error(f"推送交易失败: {e}", exc_info=True)
        return False
