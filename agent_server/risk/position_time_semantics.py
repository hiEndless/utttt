"""
给整个系统引入一个“时间耐受因子（time tolerance）”

Position Time Semantics 本质上是：
一个“时间衍生状态（derived temporal state）”，而不是事件驱动状态
这意味着：
维度	          事件型Agent	                 Position Time Semantics
触发方式	      新行情 / 新信号 / 新决策	         时间流逝
是否有“智能”	  有	                          ❌ 无
是否推理	      有	                          ❌ 无
是否决策	      有	                          ❌ 无
是否可被覆盖	  可以	                          ❌ 不应
📌 它是“事实层”，不是“认知层”。


"""


import asyncio
import json
import logging
import time
from typing import List, Dict, Any
import math

# 尝试导入 Redis 客户端，适配不同的项目结构
try:
    from agent_server.utils.redis_client import get_redis_client
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
    from agent_server.utils.redis_client import get_redis_client

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def generate_position_time_semantics(
    *,
    open_ts: int,
    now_ts: int,
    liquidation_distance_pct: float,
    exposure_pct: float,
    pnl_pct: float,
    pnl_history: List[float] | None = None
) -> Dict[str, Any]:
    """
    生成 Position Time Semantics（纯函数，风险语义版）
    """

    # -----------------------------
    # 1. 时间维度
    # -----------------------------
    holding_seconds = max(0, now_ts - open_ts)

    if holding_seconds < 3600 * 8:
        holding_class = "short"
    elif holding_seconds < 3600 * 24:
        holding_class = "medium"
    elif holding_seconds < 7 * 86400:
        holding_class = "long"
    else:
        holding_class = "extended"

    # -----------------------------
    # 2. 强平距离风险（核心）
    # -----------------------------
    if liquidation_distance_pct < 0.02:
        liquidation_risk = "critical"
    elif liquidation_distance_pct < 0.05:
        liquidation_risk = "high"
    elif liquidation_distance_pct < 0.15:
        liquidation_risk = "medium"
    else:
        liquidation_risk = "low"

    # -----------------------------
    # 3. 账户影响面（不是危险度）
    # -----------------------------
    if exposure_pct < 0.3:
        exposure_class = "limited"
    elif exposure_pct < 0.7:
        exposure_class = "significant"
    else:
        exposure_class = "dominant"

    # -----------------------------
    # 4. PnL 行为
    # -----------------------------
    if pnl_pct > 0.002:
        pnl_direction = "profit"
    elif pnl_pct < -0.002:
        pnl_direction = "loss"
    else:
        pnl_direction = "flat"

    abs_pnl = abs(pnl_pct)
    print(pnl_pct)
    if abs_pnl < 0.1:
        pnl_magnitude = "small"
    elif abs_pnl < 0.3:
        pnl_magnitude = "moderate"
    else:
        pnl_magnitude = "large"

    # -----------------------------
    # 5. PnL 稳定性
    # -----------------------------
    pnl_stability = "stable"

    if pnl_history and len(pnl_history) >= 3:
        deltas = [pnl_history[i + 1] - pnl_history[i] for i in range(len(pnl_history) - 1)]
        avg_delta = sum(deltas) / len(deltas)

        mean = sum(pnl_history) / len(pnl_history)
        variance = sum((x - mean) ** 2 for x in pnl_history) / len(pnl_history)
        volatility = math.sqrt(variance)

        if avg_delta > 0.001:
            pnl_stability = "improving"
        elif avg_delta < -0.001:
            pnl_stability = "deteriorating"

        if volatility > 0.02:
            pnl_stability = "deteriorating"

    # -----------------------------
    # 6. 时间 × 风险 综合语义
    # -----------------------------
    time_risk_flag = "none"

    if liquidation_risk in ("critical", "high"):
        time_risk_flag = "liquidation_pressure"

    elif holding_class in ("long", "extended") \
        and liquidation_risk == "low" \
        and pnl_direction == "loss" \
        and pnl_magnitude == "small" \
        and pnl_stability == "stable":
        time_risk_flag = "capital_inefficiency"

    elif pnl_stability == "deteriorating" and liquidation_risk != "low":
        time_risk_flag = "attention"

    return {
        "position_time_semantics": {
            "holding_seconds": holding_seconds,
            "holding_class": holding_class,
            "risk": {
                "liquidation_distance_pct": round(liquidation_distance_pct, 4),
                "liquidation_risk": liquidation_risk,
                "account_exposure_pct": round(exposure_pct, 4),
                "exposure_class": exposure_class,
            },
            "pnl_behavior": {
                "direction": pnl_direction,
                "magnitude": pnl_magnitude,
                "stability": pnl_stability
            },
            "time_risk_flag": time_risk_flag
        }
    }


async def fetch_positions_and_balance(exchange: str = "binance"):
    """
    从 Redis 读取持仓和账户余额
    """
    redis = get_redis_client()
    
    # 1. 获取账户权益
    balance_key = f"balance:{exchange}"
    balance_data = await redis.get(balance_key)
    total_balance = 0.0
    
    if balance_data:
        try:
            balance_json = json.loads(balance_data)
            # 优先使用 totalMarginBalance, 其次 balance
            total_balance = float(balance_json.get("balance", 0.0))
        except Exception as e:
            logger.error(f"Failed to parse balance: {e}")
            
    if total_balance <= 0:
        logger.warning(f"Total balance is 0 or invalid for {exchange}, defaulting to 1000.0 for pct calculation")
        total_balance = 1000.0  # 防止除以零，给个默认值
        
    # 2. 获取持仓列表
    positions_key = f"positions:{exchange}"
    positions_data = await redis.get(positions_key)
    positions = []
    
    if positions_data:
        try:
            positions = json.loads(positions_data)
        except Exception as e:
            logger.error(f"Failed to parse positions: {e}")
            
    return positions, total_balance


async def process_positions(exchange: str = "binance", save_to_redis: bool = True):
    """
    主处理逻辑：读取 -> 计算 -> (保存)
    """
    logger.info(f"Starting position time semantics analysis for {exchange}...")
    
    positions, total_balance = await fetch_positions_and_balance(exchange)
    
    if not positions:
        logger.info("No active positions found.")
        return

    logger.info(f"Found {len(positions)} positions. Total Balance: {total_balance}")
    
    redis = get_redis_client()
    now_ts = int(time.time())
    
    for pos in positions:
        symbol = pos.get("symbol")
        if not symbol:
            continue
            
        # 提取关键字段
        try:
            # 时间：Redis 里通常是毫秒
            open_time_ms = float(pos.get("open_time", 0))
            open_ts = int(open_time_ms / 1000) if open_time_ms > 0 else now_ts
            
            # 盈亏：pnl_ratio 是小数 (e.g. 0.05)
            pnl_pct = float(pos.get("pnl_ratio", 0.0))
            
            # 仓位规模：占用保证金 / 总权益
            initial_margin = float(pos.get("initialMargin", 0.0))
            if initial_margin == 0 and "notional" in pos and "leverage" in pos:
                 # Fallback: notional / leverage
                 initial_margin = float(pos.get("notional", 0)) / float(pos.get("leverage", 1))

            mark_price = float(pos.get("markPrice", 0))
            liq_price = float(pos.get("liquidationPrice", 0))
            notional = float(pos.get("notional", 0))

            if mark_price > 0 and liq_price > 0:
                liquidation_distance_pct = abs(mark_price - liq_price) / mark_price
            else:
                liquidation_distance_pct = 1.0  # 视为安全兜底

            exposure_pct = notional / total_balance if total_balance > 0 else 0.0
            
            # 历史 PnL：目前暂无数据源，设为 None
            pnl_history = None 
            
            # 生成语义
            semantics = generate_position_time_semantics(
                open_ts=open_ts,
                now_ts=now_ts,
                liquidation_distance_pct=liquidation_distance_pct,
                exposure_pct=exposure_pct,
                pnl_pct=pnl_pct,
                pnl_history=None
            )
            
            logger.info(f"[{symbol}] Semantics: {json.dumps(semantics, ensure_ascii=False)}")
            
            if save_to_redis:
                trade_id = pos.get("trade_id")
                if trade_id:
                    # 存入 risk:time_semantics:{exchange}:{symbol}:{trade_id}
                    key = f"risk:time_semantics:{exchange}:{symbol}:{trade_id}"
                    await redis.set(key, json.dumps(semantics), ex=300)  # 5分钟过期
                    logger.info(f"Saved semantics to {key}")
                else:
                    logger.warning(f"Missing trade_id for {symbol}, skipping save.")
                
        except Exception as e:
            logger.error(f"Error processing position {symbol}: {e}")

    logger.info("Processing complete.")


if __name__ == "__main__":
    try:
        asyncio.run(process_positions())
    except KeyboardInterrupt:
        pass

