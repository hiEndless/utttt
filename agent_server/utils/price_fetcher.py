"""
Price Fetcher 组件
用于统一获取 mark_price，支持从不同来源提取价格
"""

import json
import logging
from typing import Optional, Dict, Any
from agent_server.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)  # 减少噪音，只显示错误


async def get_mark_price(
        event_info: Dict[str, Any],
        exchange: str = "binance"
) -> Optional[float]:
    """
    统一获取 mark_price
    
    优先级：
    1. 如果是 "trade" 事件，从 event_info 的 trade_details 中提取
    2. 否则从 Redis price:{exchange}:{symbol} 中读取
    
    :param event_info: 事件信息字典，包含 route, symbol, meta 等字段
    :param exchange: 交易所名称，默认 binance
    :return: mark_price (float) 或 None
    
    使用示例：
    ```python
    # 在 final_listen_main.py 中
    mark_price = await get_mark_price(info, exchange)
    ```
    """
    try:
        route = event_info.get("route", "").lower()
        symbol = event_info.get("symbol", "")

        if not symbol:
            logger.debug("缺少 symbol 字段，无法获取 mark_price")
            return None

        # 1. 如果是 trade 事件，从 trade_details 中提取
        if route == "trade":
            # 优先从 event_info 顶层的 trade_details 提取 (由 final_listen_main 解析)
            trade_details = event_info.get("trade_details", {})

            if trade_details:
                mark_price_str = trade_details.get("mark_price")
                if mark_price_str:
                    mark_price = float(mark_price_str)
                    logger.debug(f"从 trade_details 提取 mark_price: {mark_price} ({symbol})")
                    return mark_price

        # 2. 从 Redis 读取 price:{exchange}:{symbol}
        redis_client = RedisClient()
        price_key = f"price:{exchange}:{symbol}"

        try:
            try:
                price_data_str = await redis_client.get(price_key)
            except Exception as e:
                if "WRONGTYPE" in str(e):
                    # 如果是 WRONGTYPE，说明可能是 Hash 结构，尝试用 hget 读取
                    price_str = await redis_client.client.hget(price_key, "price")
                    if price_str:
                        mark_price = float(price_str)
                        logger.debug(f"从 Redis Hash 读取 mark_price: {mark_price} ({symbol})")
                        return mark_price
                    else:
                        logger.debug(f"Redis Hash 中未找到 price 字段: {price_key}")
                        return None
                # 其他错误抛出
                raise e

            if not price_data_str:
                logger.debug(f"Redis 中未找到价格数据: {price_key}")
                return None

            # 价格数据可能是 Hash 结构（通过 HGET）或者 JSON 字符串
            # 先尝试解析为 JSON（如果是通过 GET 读取的）
            try:
                price_data = json.loads(price_data_str)
                mark_price = float(price_data.get("price", 0))
            except (json.JSONDecodeError, TypeError):
                # 如果不是 JSON，尝试直接转换为 float
                mark_price = float(price_data_str)

            if mark_price > 0:
                logger.debug(f"从 Redis 读取 mark_price: {mark_price} ({symbol})")
                return mark_price
            else:
                logger.debug(f"Redis 中的 price 无效: {mark_price} ({symbol})")
                return None

        except Exception as e:
            logger.error(f"从 Redis 读取价格失败: {e}, key={price_key}")
            return None

    except Exception as e:
        logger.error(f"获取 mark_price 失败: {e}")
        return None


async def get_mark_price_from_redis(
        exchange: str,
        symbol: str,
        use_hash: bool = True
) -> Optional[float]:
    """
    直接从 Redis 读取 mark_price（工具方法）
    
    :param exchange: 交易所名称
    :param symbol: 交易对
    :param use_hash: 是否使用 HGET 读取（Redis Hash 结构）
    :return: mark_price (float) 或 None
    
    使用示例：
    ```python
    # 方式1: Hash 结构（推荐）
    price = await get_mark_price_from_redis("binance", "BTCUSDT", use_hash=True)
    
    # 方式2: 普通 GET
    price = await get_mark_price_from_redis("binance", "BTCUSDT", use_hash=False)
    ```
    """
    try:
        redis_client = RedisClient()
        price_key = f"price:{exchange}:{symbol}"

        if use_hash:
            # 使用 HGET 读取 Hash 结构的 price 字段
            # 注意：RedisClient 的 get() 方法默认使用 GET，需要直接访问 Redis
            price_str = await redis_client.client.hget(price_key, "price")

            if price_str:
                try:
                    mark_price = float(price_str)
                    logger.debug(f"从 Redis Hash 读取 mark_price: {mark_price} ({symbol})")
                    return mark_price
                except (ValueError, TypeError):
                    logger.debug(f"价格格式无效: {price_str} ({symbol})")
                    return None
            else:
                logger.debug(f"Redis Hash 中未找到 price 字段: {price_key}")
                return None
        else:
            # 使用 GET 读取普通字符串或 JSON
            price_data_str = await redis_client.get(price_key)

            if not price_data_str:
                logger.debug(f"Redis 中未找到价格数据: {price_key}")
                return None

            try:
                price_data = json.loads(price_data_str)
                mark_price = float(price_data.get("price", 0))
            except (json.JSONDecodeError, TypeError):
                mark_price = float(price_data_str)

            if mark_price > 0:
                logger.debug(f"从 Redis 读取 mark_price: {mark_price} ({symbol})")
                return mark_price
            else:
                logger.debug(f"Redis 中的 price 无效: {mark_price} ({symbol})")
                return None

    except Exception as e:
        logger.error(f"从 Redis 读取价格失败: {e}, key=price:{exchange}:{symbol}")
        return None


# 同步版本（用于兼容同步代码）
def get_mark_price_sync(
        event_info: Dict[str, Any],
        exchange: str = "binance"
) -> Optional[float]:
    """
    同步版本的 get_mark_price（不推荐使用，仅用于兼容旧代码）
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(get_mark_price(event_info, exchange))
    except RuntimeError:
        # 如果没有事件循环，创建一个新的
        return asyncio.run(get_mark_price(event_info, exchange))


if __name__ == "__main__":
    symbol = "BTCUSDT"
    exchange = "binance"
    mark_price = get_mark_price_sync({"symbol": symbol, "exchange": exchange}, exchange)
    print(f"{symbol} 的最新价格是: {mark_price}")
