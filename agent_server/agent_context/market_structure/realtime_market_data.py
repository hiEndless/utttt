"""
实时市场数据模块：整合大订单、爆仓数据等实时市场行为
用于增强交易决策的实时性
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from agent_server.utils.redis_client import get_redis_client


async def read_force_stats(exchange: str,
                           symbol: str,
                           client: Optional[object] = None) -> Dict[str, Any]:
    """
    读取爆仓统计数据
    
    Returns:
        {
            "SELL": int,  # 多单爆仓次数
            "BUY": int,   # 空单爆仓次数
            "SELL_QTY": float,  # 多单爆仓总量
            "BUY_QTY": float,   # 空单爆仓总量
            "timestamp": int,    # 最后更新时间戳
            "liquidation_pressure": str,  # "buy_dominant" | "sell_dominant" | "balanced" | "none"
            "liquidation_intensity": str,  # "high" | "medium" | "low" | "none"
        }
    """
    cli = client or get_redis_client()
    key = f"force_stats:{exchange}:{symbol}"

    try:
        raw = await cli.get(key)
        if not raw:
            # 如果force_stats不存在，返回空数据（某些币种可能没有爆仓数据是正常的）
            return {
                "SELL": 0,
                "BUY": 0,
                "SELL_QTY": 0.0,
                "BUY_QTY": 0.0,
                "timestamp": 0,
                "liquidation_pressure": "none",
                "liquidation_intensity": "none",
            }

        stats = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(stats, dict):
            # 如果数据格式不对，返回空数据
            return {
                "SELL": 0,
                "BUY": 0,
                "SELL_QTY": 0.0,
                "BUY_QTY": 0.0,
                "timestamp": 0,
                "liquidation_pressure": "none",
                "liquidation_intensity": "none",
            }

        # 计算爆仓压力方向
        total_count = stats.get("SELL", 0) + stats.get("BUY", 0)
        total_qty = stats.get("SELL_QTY", 0.0) + stats.get("BUY_QTY", 0.0)

        liquidation_pressure = "none"
        if total_count > 0:
            sell_ratio = stats.get("SELL", 0) / total_count
            buy_ratio = stats.get("BUY", 0) / total_count
            if sell_ratio > 0.65:  # 多单爆仓占主导
                liquidation_pressure = "sell_dominant"  # 多单爆仓多 → 下行压力
            elif buy_ratio > 0.65:  # 空单爆仓占主导
                liquidation_pressure = "buy_dominant"  # 空单爆仓多 → 上行压力
            else:
                liquidation_pressure = "balanced"

        # 计算爆仓强度
        liquidation_intensity = "none"
        if total_count > 0:
            # 基于最近3分钟的数据判断强度
            ts = stats.get("timestamp", 0)
            now_ms = int(time.time() * 1000)
            age_ms = now_ms - ts

            if age_ms < 180000:  # 3分钟内
                if total_count >= 50 or total_qty >= 1000000:  # 阈值可调整
                    liquidation_intensity = "high"
                elif total_count >= 20 or total_qty >= 500000:
                    liquidation_intensity = "medium"
                elif total_count > 0:
                    liquidation_intensity = "low"

        return {
            "SELL": stats.get("SELL", 0),
            "BUY": stats.get("BUY", 0),
            "SELL_QTY": float(stats.get("SELL_QTY", 0.0)),
            "BUY_QTY": float(stats.get("BUY_QTY", 0.0)),
            "timestamp": stats.get("timestamp", 0),
            "liquidation_pressure": liquidation_pressure,
            "liquidation_intensity": liquidation_intensity,
        }
    except Exception as e:
        return {
            "SELL": 0,
            "BUY": 0,
            "SELL_QTY": 0.0,
            "BUY_QTY": 0.0,
            "timestamp": 0,
            "liquidation_pressure": "none",
            "liquidation_intensity": "none",
            "error": str(e),
        }


async def extract_large_orders_from_aggtrades(
    exchange: str,
    symbol: str,
    window_ms: int = 60000,  # 默认1分钟窗口
    large_order_threshold_usdt: float = 1000.0,  # 默认1000美元以上为大订单（降低阈值以适应小币种）
    client: Optional[object] = None,
) -> Dict[str, Any]:
    """
    从aggtrades流中提取大订单
    
    Args:
        window_ms: 时间窗口（毫秒）
        large_order_threshold_usdt: 大订单阈值（USDT价值）
    
    Returns:
        {
            "large_buy_orders": [
                {"price": float, "qty": float, "value_usdt": float, "ts": int},
                ...
            ],
            "large_sell_orders": [
                {"price": float, "qty": float, "value_usdt": float, "ts": int},
                ...
            ],
            "total_buy_value": float,
            "total_sell_value": float,
            "buy_sell_ratio": float,  # >1表示买入主导，<1表示卖出主导
            "large_order_intensity": str,  # "high" | "medium" | "low" | "none"
        }
    """
    cli = client or get_redis_client()
    key = f"aggtrades:{exchange}:{symbol}"

    now_ms = int(time.time() * 1000)
    since_ms = now_ms - window_ms

    try:
        # 检查key是否存在
        exists = await cli.exists(key)
        if not exists:
            # Key不存在，返回空数据
            return {
                "large_buy_orders": [],
                "large_sell_orders": [],
                "total_buy_value": 0.0,
                "total_sell_value": 0.0,
                "buy_sell_ratio": 0.0,
                "large_order_intensity": "none",
            }

        # 读取最近的数据
        rows = await cli.xrevrange(key, max="+", min="-", count=10000)
    except Exception as e:
        # 如果流不存在或读取失败，返回空数据
        rows = []
        # 记录错误以便调试（但不抛出异常，因为某些币种可能没有aggtrades流是正常的）
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"[realtime_market_data] 读取aggtrades失败: {key}, 错误: {e}")

    large_buy_orders = []
    large_sell_orders = []
    total_buy_value = 0.0
    total_sell_value = 0.0

    for entry_id, fields in reversed(rows or []):
        if not isinstance(fields, dict):
            continue

        try:
            # 解析时间戳
            ts_raw = fields.get("ts", 0)
            if not ts_raw:
                continue

            try:
                ts = int(float(ts_raw))
            except (ValueError, TypeError):
                # 如果ts字段不存在或格式不对，尝试从entry_id解析
                # Redis stream entry_id格式: timestamp-sequence
                try:
                    entry_id_str = str(entry_id) if entry_id else ""
                    if "-" in entry_id_str:
                        ts = int(entry_id_str.split("-")[0])
                    else:
                        continue
                except:
                    continue

            if ts < since_ms:
                continue

            # 解析价格和数量
            price_raw = fields.get("price", 0)
            qty_raw = fields.get("qty", 0)
            is_buyer_maker_raw = fields.get("is_buyer_maker", 0)

            try:
                price = float(price_raw)
                qty = float(qty_raw)
                is_buyer_maker = bool(int(is_buyer_maker_raw))
            except (ValueError, TypeError):
                continue

            if price <= 0 or qty <= 0:
                continue

            value_usdt = price * qty

            # 判断是否为大订单
            if value_usdt >= large_order_threshold_usdt:
                order_info = {
                    "price": price,
                    "qty": qty,
                    "value_usdt": value_usdt,
                    "ts": ts,
                }

                # is_buyer_maker=True 表示买方是maker（被动成交），实际是卖出
                # is_buyer_maker=False 表示卖方是maker（被动成交），实际是买入
                if is_buyer_maker:
                    # 卖方主动，属于卖出大单
                    large_sell_orders.append(order_info)
                    total_sell_value += value_usdt
                else:
                    # 买方主动，属于买入大单
                    large_buy_orders.append(order_info)
                    total_buy_value += value_usdt

        except Exception as e:
            # 记录解析错误但不中断处理
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(
                f"[realtime_market_data] 解析aggtrades记录失败: {e}, fields={fields}"
            )
            continue

    # 计算买卖比例
    total_value = total_buy_value + total_sell_value
    buy_sell_ratio = (total_buy_value /
                      total_sell_value) if total_sell_value > 0 else (
                          total_buy_value / 1.0)

    # 计算大订单强度（降低阈值以适应小币种）
    large_order_intensity = "none"
    if total_value > 0:
        if total_value >= large_order_threshold_usdt * 5:  # 5倍阈值以上为high
            large_order_intensity = "high"
        elif total_value >= large_order_threshold_usdt * 2:  # 2倍阈值以上为medium
            large_order_intensity = "medium"
        elif total_value >= large_order_threshold_usdt * 0.5:  # 0.5倍阈值以上为low
            large_order_intensity = "low"

    return {
        "large_buy_orders": large_buy_orders[:20],  # 最多返回20个
        "large_sell_orders": large_sell_orders[:20],
        "total_buy_value": total_buy_value,
        "total_sell_value": total_sell_value,
        "buy_sell_ratio": buy_sell_ratio,
        "large_order_intensity": large_order_intensity,
        "window_ms": window_ms,
        "threshold_usdt": large_order_threshold_usdt,
    }


async def build_realtime_market_data(exchange: str,
                                     symbol: str) -> Dict[str, Any]:
    """
    构建实时市场数据（大订单 + 爆仓数据）
    
    Returns:
        {
            "liquidation": {...},  # 爆仓数据
            "large_orders": {...},  # 大订单数据
            "realtime_signals": {
                "buy_pressure": str,  # "strong" | "moderate" | "weak" | "none"
                "sell_pressure": str,
                "liquidation_risk": str,  # "high" | "medium" | "low" | "none"
            }
        }
    """
    client = get_redis_client()

    # 并行读取
    liquidation_task = read_force_stats(exchange, symbol, client)
    large_orders_task = extract_large_orders_from_aggtrades(exchange,
                                                            symbol,
                                                            client=client)

    liquidation_data, large_orders_data = await asyncio.gather(
        liquidation_task,
        large_orders_task,
    )

    # 综合判断实时信号
    buy_pressure = "none"
    sell_pressure = "none"
    liquidation_risk = "none"

    # 基于大订单判断买卖压力
    buy_sell_ratio = large_orders_data.get("buy_sell_ratio", 1.0)
    large_order_intensity = large_orders_data.get("large_order_intensity",
                                                  "none")

    if large_order_intensity != "none":
        if buy_sell_ratio > 2.0:
            buy_pressure = "strong"
        elif buy_sell_ratio > 1.5:
            buy_pressure = "moderate"
        elif buy_sell_ratio > 1.0:
            buy_pressure = "weak"
        elif buy_sell_ratio < 0.5:
            sell_pressure = "strong"
        elif buy_sell_ratio < 0.67:
            sell_pressure = "moderate"
        elif buy_sell_ratio < 1.0:
            sell_pressure = "weak"

    # 基于爆仓数据判断风险
    liquidation_intensity = liquidation_data.get("liquidation_intensity",
                                                 "none")
    liquidation_pressure = liquidation_data.get("liquidation_pressure", "none")

    if liquidation_intensity == "high":
        liquidation_risk = "high"
    elif liquidation_intensity == "medium":
        liquidation_risk = "medium"
    elif liquidation_intensity == "low":
        liquidation_risk = "low"

    # 如果爆仓压力与信号方向一致，可能放大趋势
    # 如果爆仓压力与信号方向相反，可能形成反转风险

    return {
        "liquidation": liquidation_data,
        "large_orders": large_orders_data,
        "realtime_signals": {
            "buy_pressure": buy_pressure,
            "sell_pressure": sell_pressure,
            "liquidation_risk": liquidation_risk,
            "liquidation_pressure": liquidation_pressure,
        },
        "ts": int(time.time() * 1000),
    }


if __name__ == "__main__":
    import asyncio

    async def test():
        data = await build_realtime_market_data("binance", "BTCUSDT")
        print(json.dumps(data, ensure_ascii=False, indent=2))

    asyncio.run(test())
