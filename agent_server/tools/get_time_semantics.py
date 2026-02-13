import json
import logging
from typing import Dict, Any, Optional

try:
    from agent_server.utils.redis_client import get_redis_client
except ImportError:
    import sys
    import os

    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
    from agent_server.utils.redis_client import get_redis_client

logger = logging.getLogger(__name__)


async def get_position_time_semantics(
        exchange: str,
        symbol: str,
        trade_id: str
) -> Optional[Dict[str, Any]]:
    """
    从 Redis 读取 Position Time Semantics

    Key: risk:time_semantics:{exchange}:{symbol}:{trade_id}

    Args:
        exchange (str): 交易所名称 (e.g., "binance")
        symbol (str): 交易对 (e.g., "ETHUSDT")
        trade_id (str): 交易ID

    Returns:
        Optional[Dict[str, Any]]: 如果存在且解析成功，返回字典；否则返回 None
    """
    try:
        redis = get_redis_client()
        key = f"risk:time_semantics:{exchange}:{symbol}:{trade_id}"

        data = await redis.get(key)

        if not data:
            return None

        try:
            return json.loads(data)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from key: {key}, data: {data}")
            return None

    except Exception as e:
        logger.error(f"Error fetching position time semantics for {key}: {e}")
        return None


if __name__ == "__main__":
    import asyncio


    async def demo():
        res = await get_position_time_semantics("binance", "ETHUSDT", "1f9d3feb1dff4fda9c4462eb71e2f21f")
        print(f"Result: {res}")


    asyncio.run(demo())
