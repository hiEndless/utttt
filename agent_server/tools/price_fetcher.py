"""
Price Fetcher 组件
用于统一获取 mark_price。Redis 中的 price:binance:{symbol} 由 market_ws 用 REST ticker 写入，
此处优先读 Redis，缺失或过期时用 REST 回退并写回。
"""

import json
import logging
import time
import os
from typing import Optional, Dict, Any
from agent_server.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)

STALE_SECONDS = 15
BINANCE_TICKER_URL_MAIN = "https://fapi.binance.com/fapi/v1/ticker/price"
BINANCE_TICKER_URL_TEST = "https://testnet.binancefuture.com/fapi/v1/ticker/price"


async def _fetch_ticker_price_rest(exchange: str, symbol: str) -> Optional[float]:
    """从交易所 REST 获取最新成交价（ticker/price）。"""
    if exchange != "binance":
        return None
    try:
        from agent_server.utils.http_client import http_client
        use_testnet = os.environ.get("BINANCE_TESTNET", "true").strip().lower() in ("1", "true", "yes", "on")
        url = BINANCE_TICKER_URL_TEST if use_testnet else BINANCE_TICKER_URL_MAIN
        data = await http_client.request("GET", url, params={"symbol": symbol})
        if isinstance(data, dict) and "price" in data:
            return float(data["price"])
        return None
    except Exception as e:
        logger.warning(f"REST ticker 获取失败 {exchange} {symbol}: {e}")
        return None


async def _write_price_to_redis(price_key: str, price: float) -> None:
    """将 REST 获取的价格写回 Redis（与 market_ws 相同的 Hash 结构）。"""
    try:
        redis_client = RedisClient()
        now_ms = int(time.time() * 1000)
        await redis_client.client.hset(
            price_key,
            mapping={"ts": str(now_ms), "price": str(price)}
        )
        logger.debug(f"已写回 Redis 价格: key={price_key} price={price}")
    except Exception as e:
        logger.warning(f"写回 Redis 价格失败: {e}")


async def get_mark_price(
        event_info: Dict[str, Any],
        exchange: str = "binance"
) -> Optional[float]:
    """
    统一获取 mark_price。优先级：
    1. trade 事件：从 trade_details.mark_price 提取
    2. 从 Redis price:{exchange}:{symbol} 读取（由 market_ws REST ticker 写入）
    3. 缺失或过期时用 REST ticker 回退并写回
    """
    try:
        route = event_info.get("route", "").lower()
        symbol = event_info.get("symbol", "")

        if not symbol:
            logger.warning("缺少 symbol 字段，无法获取 mark_price")
            return None

        # 1. trade 事件：从 trade_details 提取
        if route == "trade":
            trade_details = event_info.get("trade_details", {})
            if trade_details:
                mark_price_str = trade_details.get("mark_price")
                if mark_price_str:
                    mark_price = float(mark_price_str)
                    logger.debug(f"从 trade_details 提取 mark_price: {mark_price} ({symbol})")
                    return mark_price

        # 2. 从 Redis 读取；缺失或过期时 REST 回退并写回
        redis_client = RedisClient()
        price_key = f"price:{exchange}:{symbol}"
        redis_price: Optional[float] = None
        redis_ts_ms: Optional[int] = None

        try:
            price_str = await redis_client.client.hget(price_key, "price")
            ts_str = await redis_client.client.hget(price_key, "ts")
            if price_str:
                redis_price = float(price_str)
            if ts_str:
                try:
                    redis_ts_ms = int(float(ts_str))
                except (TypeError, ValueError):
                    pass

            now_s = time.time()
            if redis_price is not None and redis_price > 0:
                if redis_ts_ms is not None:
                    age_s = now_s - redis_ts_ms / 1000.0
                    if age_s <= STALE_SECONDS:
                        logger.debug(f"从 Redis 读取 mark_price: {redis_price} ({symbol}), 滞后 {age_s:.1f}s")
                        return redis_price
                    logger.info(f"Redis 价格已过期 ({age_s:.1f}s)，REST 回退: {symbol}")

            rest_price = await _fetch_ticker_price_rest(exchange, symbol)
            if rest_price is not None and rest_price > 0:
                await _write_price_to_redis(price_key, rest_price)
                return rest_price
            if redis_price is not None and redis_price > 0:
                logger.warning(f"REST ticker 失败，使用 Redis 旧价: {redis_price} ({symbol})")
                return redis_price
            logger.warning(f"无法获取价格: Redis 无有效数据且 REST 失败 ({symbol})")
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
                mark_price = float(price_str)
                logger.debug(f"从 Redis Hash 读取 mark_price: {mark_price} ({symbol})")
                return mark_price
            else:
                logger.warning(f"Redis Hash 中未找到 price 字段: {price_key}")
                return None
        else:
            # 使用 GET 读取普通字符串或 JSON
            price_data_str = await redis_client.get(price_key)

            if not price_data_str:
                logger.warning(f"Redis 中未找到价格数据: {price_key}")
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
                logger.warning(f"Redis 中的 price 无效: {mark_price} ({symbol})")
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
