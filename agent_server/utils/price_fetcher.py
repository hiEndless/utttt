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
        use_hash: bool = True,
        db: int | None = None
) -> Optional[float]:
    """
    直接从 Redis 读取 mark_price（工具方法）
    
    :param exchange: 交易所名称
    :param symbol: 交易对
    :param use_hash: 是否使用 HGET 读取（Redis Hash 结构）
    :param db: 指定 Redis DB，如果为 None 则使用 settings.redis_db
    :return: mark_price (float) 或 None
    
    使用示例：
    ```python
    # 方式1: Hash 结构（推荐）
    price = await get_mark_price_from_redis("binance", "BTCUSDT", use_hash=True)
    
    # 方式2: 普通 GET
    price = await get_mark_price_from_redis("binance", "BTCUSDT", use_hash=False)
    
    # 方式3: 指定 DB
    price = await get_mark_price_from_redis("binance", "BTCUSDT", db=1)
    ```
    """
    try:
        # 如果指定了 db，使用指定的 DB；否则使用默认配置
        from agent_server.config import settings
        current_db = db if db is not None else settings.redis_db
        redis_client = RedisClient(db=db) if db is not None else RedisClient()
        price_key = f"price:{exchange}:{symbol}"

        if use_hash:
            # 使用 HGET 读取 Hash 结构的 price 字段
            # 注意：RedisClient 的 get() 方法默认使用 GET，需要直接访问 Redis
            price_str = await redis_client.client.hget(price_key, "price")

            if price_str:
                try:
                    mark_price = float(price_str)
                    logger.debug(f"从 Redis Hash 读取 mark_price: {mark_price} ({symbol}) | DB={current_db}")
                    return mark_price
                except (ValueError, TypeError):
                    logger.debug(f"价格格式无效: {price_str} ({symbol})")
                    return None
            else:
                logger.warning(f"Redis Hash 中未找到 price 字段: {price_key} | DB={current_db}")
                # 尝试从其他 DB 读取（DB 8 -> DB 1）
                if db is None:
                    db_candidates = [8, 1]
                    db_candidates = [d for d in db_candidates if d != current_db]  # 排除已尝试的 DB
                    
                    for try_db in db_candidates:
                        try:
                            logger.debug(f"尝试从 DB {try_db} 读取价格数据...")
                            redis_client_try = RedisClient(db=try_db)
                            price_str_try = await redis_client_try.client.hget(price_key, "price")
                            if price_str_try:
                                mark_price = float(price_str_try)
                                logger.info(f"从 DB {try_db} 读取到价格: {mark_price} ({symbol})")
                                return mark_price
                        except Exception as e:
                            logger.debug(f"从 DB {try_db} 读取失败: {e}")
                            continue
                return None
        else:
            # 使用 GET 读取普通字符串或 JSON
            price_data_str = await redis_client.get(price_key)

            if not price_data_str:
                logger.warning(f"Redis 中未找到价格数据: {price_key} | DB={current_db}")
                # 尝试从其他 DB 读取（DB 8 -> DB 1）
                if db is None:
                    db_candidates = [8, 1]
                    db_candidates = [d for d in db_candidates if d != current_db]  # 排除已尝试的 DB
                    
                    for try_db in db_candidates:
                        try:
                            logger.debug(f"尝试从 DB {try_db} 读取价格数据...")
                            redis_client_try = RedisClient(db=try_db)
                            price_data_str = await redis_client_try.get(price_key)
                            if price_data_str:
                                logger.info(f"从 DB {try_db} 读取到价格数据: {symbol}")
                                break
                        except Exception as e:
                            logger.debug(f"从 DB {try_db} 读取失败: {e}")
                            continue
                    
                    if not price_data_str:
                        return None
                else:
                    return None

            try:
                price_data = json.loads(price_data_str)
                mark_price = float(price_data.get("price", 0))
            except (json.JSONDecodeError, TypeError):
                mark_price = float(price_data_str)

            if mark_price > 0:
                logger.debug(f"从 Redis 读取 mark_price: {mark_price} ({symbol}) | DB={current_db}")
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
