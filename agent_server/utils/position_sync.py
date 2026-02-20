"""
个人仓位检查与 Redis 清理工具
- 从 positions:{exchange} 获取真实仓位
- 对比 trading:open_positions:{exchange}，清理无持仓的 symbol
"""
import json
import logging
from typing import List, Set

logger = logging.getLogger("position_sync")

POSITIONS_KEY = "positions"
OPEN_POSITIONS_KEY = "trading:open_positions"


def get_real_position_symbols(positions_data: List[dict]) -> Set[str]:
    """
    从仓位数据中提取有持仓的 symbol 集合（positionAmt != 0）
    """
    symbols = set()
    for p in positions_data or []:
        if not isinstance(p, dict):
            continue
        amt = p.get("positionAmt") or p.get("position_amt") or 0
        try:
            if float(amt) != 0:
                sym = p.get("symbol", "")
                if sym:
                    symbols.add(str(sym))
        except (ValueError, TypeError):
            pass
    return symbols


async def sync_open_positions_with_reality(
    exchange: str = "binance",
    redis_client=None,
) -> int:
    """
    根据真实仓位同步 trading:open_positions，清理已平仓的 symbol

    Args:
        exchange: 交易所
        redis_client: RedisClient 或 async Redis，None 则新建

    Returns:
        清理的 symbol 数量
    """
    if redis_client is None:
        from agent_server.utils.redis_client import RedisClient
        _rc = RedisClient()
        rc = _rc.client
    else:
        rc = redis_client.client if hasattr(redis_client, "client") else redis_client

    position_key = f"{OPEN_POSITIONS_KEY}:{exchange}"
    positions_key = f"{POSITIONS_KEY}:{exchange}"

    positions_data = []
    try:
        raw = await rc.get(positions_key)
        if raw:
            data = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            positions_data = json.loads(data) if isinstance(data, str) else data
            if not isinstance(positions_data, list):
                positions_data = []
    except Exception as e:
        logger.warning(f"读取仓位失败: {e}")

    real_symbols = get_real_position_symbols(positions_data)
    recorded = await rc.smembers(position_key)
    recorded_symbols = {s.decode() if isinstance(s, bytes) else str(s) for s in (recorded or set())}

    cleared = 0
    for symbol in recorded_symbols:
        if symbol not in real_symbols:
            await rc.srem(position_key, symbol)
            cleared += 1
            logger.info(f"仓位已平仓，清理 Redis 记录: {symbol}")

    if cleared > 0:
        logger.info(f"仓位同步完成: 清理 {cleared} 个已平仓 symbol")

    return cleared


def clear_open_positions_for_symbol(exchange: str, symbol: str) -> bool:
    """清除指定 symbol 的 trading:open_positions 记录（同步版本）"""
    try:
        import redis
        from agent_server.config import settings
        r = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password,
            decode_responses=True,
        )
        key = f"{OPEN_POSITIONS_KEY}:{exchange}"
        r.srem(key, symbol)
        r.close()
        logger.info(f"已清除 trading:open_positions 记录: {symbol}")
        return True
    except Exception as e:
        logger.error(f"清除记录失败: {e}")
        return False


def clear_all_open_positions(exchange: str = "binance") -> bool:
    """清空 trading:open_positions:{exchange} 整个集合（慎用，用于重置脏数据）"""
    try:
        import redis
        from agent_server.config import settings
        r = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password,
            decode_responses=True,
        )
        key = f"{OPEN_POSITIONS_KEY}:{exchange}"
        r.delete(key)
        r.close()
        logger.info(f"已清空 {key}")
        return True
    except Exception as e:
        logger.error(f"清空失败: {e}")
        return False
