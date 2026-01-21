import asyncio
import json
import time
import os
import logging
from datetime import datetime
from typing import Dict, Optional, List
from agno.workflow import StepInput
from agent_server.agents.experts.analysis.trade_decision import TradeDecisionExpert
from agent_server.agent_workflow.components.base import BaseWorkflowComponent
from agent_server.utils.redis_client import RedisClient
from agent_server.utils.price_fetcher import get_mark_price_from_redis
import redis

# 配置 trade 决策日志
trade_logger = logging.getLogger("trade_decision")

# 推理日志配置（只配置一次，避免重复）
REASONING_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                 "logs")
os.makedirs(REASONING_LOG_DIR, exist_ok=True)

reasoning_logger = logging.getLogger("trade_reasoning")
reasoning_logger.setLevel(logging.INFO)
reasoning_logger.propagate = False

# 检查是否已经有handler，避免重复添加
if not reasoning_logger.handlers:
    # 推理日志文件handler
    reasoning_file_handler = logging.FileHandler(os.path.join(
        REASONING_LOG_DIR,
        f"trade_reasoning_{datetime.now().strftime('%Y%m%d')}.log"),
                                                 encoding='utf-8')
    reasoning_file_handler.setFormatter(
        logging.Formatter('%(asctime)s [REASONING] %(message)s',
                          datefmt='%Y-%m-%d %H:%M:%S'))
    reasoning_logger.addHandler(reasoning_file_handler)


class TradeDecisionExecutionComponent(BaseWorkflowComponent):
    """
    交易决策执行组件：
    1. 综合信号验证结果和风控建议
    2. 读取 L1 事件和市场结构数据
    3. 调用 TradeDecisionExpert 做出最终决策
    4. 如果 should_execute==true，推送到 Redis 队列 TASK_ADD_TRADE
    """

    def __init__(self):
        self.expert = TradeDecisionExpert()
        # Redis 配置（用于推送交易订单）
        self.trade_redis_config = {
            'host': '38.147.173.111',
            'port': 6379,
            'password': '112233Ww..',
            'db': 8,
            'decode_responses': False
        }
        self.trade_queue_name = 'TASK_ADD_TRADE'

    async def _fetch_l1_event(self, exchange: str,
                              symbol: str, 
                              event_id: str = None) -> Optional[Dict]:
        """
        从 l1_events stream 读取 L1 事件
        
        Args:
            exchange: 交易所名称
            symbol: 交易对符号
            event_id: 事件ID（可选），如果提供则优先匹配event_id，否则返回最新的匹配symbol的事件
        
        Returns:
            匹配的L1事件字典，如果未找到则返回None
        """
        try:
            rc = RedisClient()
            # 从 l1_events stream 读取最新事件
            stream_key = "l1_events"
            # 如果提供了event_id，读取更多事件以确保能找到匹配的
            count = 100 if event_id else 20
            res = await rc.client.xrevrange(stream_key,
                                            max="+",
                                            min="-",
                                            count=count)

            if not res:
                return None

            # 查找匹配的事件
            matched_by_event_id = None  # 精确匹配event_id的事件
            matched_by_symbol = None    # 按symbol匹配的最新事件（fallback）
            
            for entry_id, fields in res:
                event = {}
                for k, v in fields.items():
                    key = k.decode() if isinstance(k, bytes) else k
                    val = v.decode() if isinstance(v, bytes) else v
                    event[key] = val

                event_symbol = event.get("symbol", "")
                event_event_id = event.get("event_id", "")
                
                # 如果提供了event_id，优先精确匹配
                if event_id:
                    if event_event_id == event_id and event_symbol == symbol:
                        # 解析 payload 如果存在
                        if "payload" in event and isinstance(event["payload"], str):
                            try:
                                event["payload"] = json.loads(event["payload"])
                            except:
                                pass
                        matched_by_event_id = event
                        break  # 找到精确匹配，直接返回
                    # 同时记录按symbol匹配的最新事件（作为fallback）
                    elif event_symbol == symbol and matched_by_symbol is None:
                        if "payload" in event and isinstance(event["payload"], str):
                            try:
                                event["payload"] = json.loads(event["payload"])
                            except:
                                pass
                        matched_by_symbol = event
                # 如果没有提供event_id，按symbol匹配
                elif event_symbol == symbol:
                    if "payload" in event and isinstance(event["payload"], str):
                        try:
                            event["payload"] = json.loads(event["payload"])
                        except:
                            pass
                    matched_by_symbol = event
                    break  # 找到第一个匹配的symbol事件即可
            
            # 优先返回精确匹配的event_id事件
            if matched_by_event_id:
                trade_logger.debug(
                    f"找到匹配event_id的L1事件 | {symbol} | event_id={event_id} | score={matched_by_event_id.get('total_score')}"
                )
                return matched_by_event_id
            
            # 如果没有找到精确匹配，但有fallback事件，返回并记录警告
            if matched_by_symbol:
                trade_logger.warning(
                    f"未找到匹配event_id的L1事件，使用最新匹配symbol的事件 | {symbol} | 期望event_id={event_id} | 实际event_id={matched_by_symbol.get('event_id')} | score={matched_by_symbol.get('total_score')}"
                )
                return matched_by_symbol
            
            return None
        except Exception as e:
            trade_logger.debug(f"读取 L1 事件失败: {e}")
            return None

    async def _fetch_market_structure(self, exchange: str,
                                      symbol: str) -> Optional[Dict]:
        """从 Redis 读取 market_structure 数据"""
        from agent_server.config import settings

        key = f"background:{exchange}:{symbol}:market_structure"

        # 尝试的 DB 列表：当前配置的 DB -> DB 8 -> DB 1
        db_candidates = [settings.redis_db, 8, 1]
        db_candidates = list(dict.fromkeys(db_candidates))  # 去重保持顺序

        for db in db_candidates:
            try:
                rc = RedisClient(db=db)
                data_str = await rc.get(key)

                if data_str:
                    try:
                        if isinstance(data_str, str):
                            result = json.loads(data_str)
                        else:
                            result = data_str

                        if db != settings.redis_db:
                            trade_logger.debug(
                                f"从 DB {db} 读取到 market_structure | {symbol}")
                        return result
                    except json.JSONDecodeError as e:
                        trade_logger.warning(
                            f"解析 market_structure JSON 失败 | {symbol} | DB {db} | {e}"
                        )
                        continue
            except Exception as e:
                trade_logger.debug(
                    f"从 DB {db} 读取 market_structure 失败 | {symbol} | {e}")
                continue

        trade_logger.warning(
            f"未找到 market_structure | {symbol} | 已尝试 DB: {db_candidates}")
        return None

    async def _fetch_klines(self, exchange: str, symbol: str,
                            interval: str) -> List:
        """从 Redis 读取 K 线数据"""
        from agent_server.config import settings

        key = f"klines:{exchange}:{symbol}:{interval}"

        # 尝试的 DB 列表：当前配置的 DB -> DB 8 -> DB 1
        db_candidates = [settings.redis_db, 8, 1]
        db_candidates = list(dict.fromkeys(db_candidates))  # 去重保持顺序

        for db in db_candidates:
            try:
                rc = RedisClient(db=db)
                data_str = await rc.get(key)

                if data_str:
                    try:
                        if isinstance(data_str, str):
                            result = json.loads(data_str)
                        else:
                            result = data_str

                        if isinstance(result, list) and len(result) > 0:
                            if db != settings.redis_db:
                                trade_logger.debug(
                                    f"从 DB {db} 读取到 {interval} K线 | {symbol} | 数量={len(result)}"
                                )
                            return result
                    except json.JSONDecodeError as e:
                        trade_logger.debug(
                            f"解析 {interval} K线 JSON 失败 | {symbol} | DB {db} | {e}"
                        )
                        continue
            except Exception as e:
                trade_logger.debug(
                    f"从 DB {db} 读取 {interval} K线失败 | {symbol} | {e}")
                continue

        return []

    def _analyze_trend_from_klines(
            self,
            klines_15m: List,
            klines_30m: List,
            current_price: float,
            market_structure: Dict = None) -> Dict[str, any]:
        """
        根据15m和30m K线数据判断趋势方向，结合市场结构验证
        
        Args:
            klines_15m: 15分钟K线数据列表
            klines_30m: 30分钟K线数据列表
            current_price: 当前价格
            market_structure: 市场结构数据（可选，用于验证）
        
        Returns:
            {"trend": "bullish|bearish|neutral", "strength": "strong|moderate|weak", "confidence": float}
        """
        try:
            trend_signals = []

            # 分析15m趋势
            if klines_15m and len(klines_15m) >= 5:
                recent_15m = klines_15m[-20:] if len(
                    klines_15m) > 20 else klines_15m
                closes_15m = [float(k[4]) for k in recent_15m if len(k) > 4]
                if len(closes_15m) >= 5:
                    # 计算移动平均线（简单移动平均）
                    ma_short = sum(closes_15m[-5:]) / 5
                    ma_long = sum(closes_15m[-10:]) / 10 if len(
                        closes_15m) >= 10 else ma_short

                    # 判断趋势（更严格的判断：需要价格明显高于/低于均线）
                    price_vs_ma_short = (
                        closes_15m[-1] -
                        ma_short) / ma_short * 100 if ma_short > 0 else 0
                    if ma_short > ma_long and price_vs_ma_short > 0.1:  # 价格高于短期均线至少0.1%
                        trend_signals.append("bullish")
                    elif ma_short < ma_long and price_vs_ma_short < -0.1:  # 价格低于短期均线至少0.1%
                        trend_signals.append("bearish")
                    else:
                        trend_signals.append("neutral")

            # 分析30m趋势
            if klines_30m and len(klines_30m) >= 5:
                recent_30m = klines_30m[-20:] if len(
                    klines_30m) > 20 else klines_30m
                closes_30m = [float(k[4]) for k in recent_30m if len(k) > 4]
                if len(closes_30m) >= 5:
                    ma_short = sum(closes_30m[-5:]) / 5
                    ma_long = sum(closes_30m[-10:]) / 10 if len(
                        closes_30m) >= 10 else ma_short

                    price_vs_ma_short = (
                        closes_30m[-1] -
                        ma_short) / ma_short * 100 if ma_short > 0 else 0
                    if ma_short > ma_long and price_vs_ma_short > 0.1:
                        trend_signals.append("bullish")
                    elif ma_short < ma_long and price_vs_ma_short < -0.1:
                        trend_signals.append("bearish")
                    else:
                        trend_signals.append("neutral")

            # 综合判断
            bullish_count = trend_signals.count("bullish")
            bearish_count = trend_signals.count("bearish")

            # 如果市场结构存在，进行验证
            if market_structure:
                overall_bias = market_structure.get(
                    "market_participant_summary", {}).get("overall_bias", "")
                if overall_bias:
                    # 如果市场结构与K线趋势一致，提高置信度
                    if overall_bias == "long" and bullish_count > bearish_count:
                        confidence_boost = 0.1
                    elif overall_bias == "short" and bearish_count > bullish_count:
                        confidence_boost = 0.1
                    else:
                        # 如果不一致，降低置信度，可能趋势判断有误
                        confidence_boost = -0.2
                else:
                    confidence_boost = 0
            else:
                confidence_boost = 0

            if bullish_count > bearish_count:
                trend = "bullish"
                strength = "strong" if bullish_count == 2 else "moderate"
                confidence = min(
                    0.9,
                    max(0.3, (0.8 if bullish_count == 2 else 0.6) +
                        confidence_boost))
            elif bearish_count > bullish_count:
                trend = "bearish"
                strength = "strong" if bearish_count == 2 else "moderate"
                confidence = min(
                    0.9,
                    max(0.3, (0.8 if bearish_count == 2 else 0.6) +
                        confidence_boost))
            else:
                trend = "neutral"
                strength = "weak"
                confidence = 0.5

            return {
                "trend": trend,
                "strength": strength,
                "confidence": confidence
            }
        except Exception as e:
            trade_logger.warning(f"分析趋势失败: {e}")
            return {"trend": "neutral", "strength": "weak", "confidence": 0.5}

    def _calculate_tp_sl_from_klines(
            self,
            klines_5m: List,
            klines_15m: List,
            klines_30m: List,
            current_price: float,
            direction: str,
            trend_analysis: Dict = None,
            is_counter_trend: bool = False) -> Dict[str, float]:
        """
        根据15分钟K线数据计算合理的止盈止损百分比
        原则：基于15分钟周期（大周期）的支撑阻力位和ATR来计算，确保能抗住正常市场波动
        
        Args:
            klines_5m: 5分钟K线数据列表（用于参考开仓位置）
            klines_15m: 15分钟K线数据列表（主要计算周期，大周期）
            klines_30m: 30分钟K线数据列表（用于参考）
            current_price: 当前价格
            direction: 交易方向 "LONG" 或 "SHORT"
            trend_analysis: 趋势分析结果（可选）
            is_counter_trend: 是否逆势交易
        
        Returns:
            {"tp_percent": float, "sl_percent": float}
        """
        try:
            # 默认值（如果无法计算）- 提高默认值以抗住波动
            default_tp = 4.0  # 4%
            default_sl = 2.5  # 2.5%

            # 优先使用15分钟周期（大周期）计算
            if not klines_15m or len(klines_15m) < 5:
                # 如果15分钟数据不足，使用5分钟数据但提高比例
                if klines_5m and len(klines_5m) >= 5:
                    trade_logger.warning("15分钟数据不足，使用5分钟数据计算（不推荐）")
                    klines_15m = klines_5m  # 临时使用5分钟数据
                else:
                    return {"tp_percent": default_tp, "sl_percent": default_sl}

            # 分析15分钟周期的支撑阻力位和波动空间（使用最近48根，约12小时）
            recent_15m = klines_15m[-48:] if len(
                klines_15m) > 48 else klines_15m

            if len(recent_15m) < 5:
                return {"tp_percent": default_tp, "sl_percent": default_sl}

            # 提取高低点
            highs = [float(k[2]) for k in recent_15m if len(k) > 2]
            lows = [float(k[3]) for k in recent_15m if len(k) > 3]
            closes = [float(k[4]) for k in recent_15m if len(k) > 4]

            if not highs or not lows or not closes:
                return {"tp_percent": default_tp, "sl_percent": default_sl}

            max_high = max(highs)
            min_low = min(lows)
            current_close = closes[-1]

            # 计算向上和向下的空间（基于15分钟周期）
            upward_space = (max_high - current_price
                            ) / current_price * 100 if current_price > 0 else 0
            downward_space = (
                current_price -
                min_low) / current_price * 100 if current_price > 0 else 0

            # 计算15分钟的ATR（用于确定最小止损）- 这是大周期的波动性指标
            atr_15m = 0.0
            if len(recent_15m) >= 14:  # AR需要至少14根K线
                true_ranges = []
                for i in range(1, len(recent_15m)):
                    prev_close = float(recent_15m[i - 1][4]) if len(
                        recent_15m[i - 1]) > 4 else current_price
                    high = float(recent_15m[i][2]) if len(
                        recent_15m[i]) > 2 else current_price
                    low = float(recent_15m[i][3]) if len(
                        recent_15m[i]) > 3 else current_price
                    tr = max(high - low, abs(high - prev_close),
                             abs(low - prev_close))
                    true_ranges.append(tr)
                if true_ranges:
                    # 使用最近14根K线计算ATR
                    atr_15m = sum(true_ranges[-14:]) / min(
                        14, len(true_ranges))
                    atr_15m_percent = (atr_15m / current_price
                                       ) * 100 if current_price > 0 else 0
                else:
                    atr_15m_percent = 0.0
            else:
                # 数据不足时，使用简单平均波动
                if len(recent_15m) >= 2:
                    ranges = [
                        float(recent_15m[i][2]) - float(recent_15m[i][3])
                        for i in range(len(recent_15m))
                        if len(recent_15m[i]) > 3
                    ]
                    if ranges:
                        avg_range = sum(ranges) / len(ranges)
                        atr_15m_percent = (avg_range / current_price
                                           ) * 100 if current_price > 0 else 0
                    else:
                        atr_15m_percent = 0.0
                else:
                    atr_15m_percent = 0.0

            # 根据交易方向计算止盈止损（基于15分钟周期）
            if direction == "LONG":
                # 做多：止盈在上方，止损在下方
                # 止盈：基于15分钟周期的阻力位和ATR，最小3%，最大8-10%
                # 但如果向上空间很小（<2%），应该更保守，不要设置过大的TP
                tp_candidate1 = upward_space * 0.6 if upward_space > 0 else 0  # 向上空间的60%
                tp_candidate2 = atr_15m_percent * 3.0 if atr_15m_percent > 0 else 0  # 3倍ATR
                tp_min = 3.0  # 最小3%（能抗住波动）
                tp_max = 10.0 if is_counter_trend else 8.0  # 逆势交易最多10%
                
                # 如果向上空间很小（<2%），限制最大TP为向上空间的80%，避免设置不合理的TP
                if upward_space > 0 and upward_space < 2.0:
                    tp_max = min(tp_max, upward_space * 0.8)
                    tp_min = min(tp_min, upward_space * 0.5)  # 如果空间小，最小TP也相应降低
                
                tp_percent = max(tp_candidate1, tp_candidate2, tp_min)
                tp_percent = min(tp_percent, tp_max)

                # 止损：基于15分钟周期的支撑位和ATR，最小2%，最大5-6%
                # 止损要足够保险，不能被轻易清洗
                sl_candidate1 = downward_space * 0.5 if downward_space > 0 else 0  # 向下空间的50%
                sl_candidate2 = atr_15m_percent * 2.0 if atr_15m_percent > 0 else 0  # 2倍ATR
                sl_min = 3.0 if is_counter_trend else 2.0  # 逆势交易至少3%，正常至少2%
                sl_max = 6.0 if is_counter_trend else 5.0  # 逆势交易最多6%
                sl_percent = max(sl_candidate1, sl_candidate2, sl_min)
                sl_percent = min(sl_percent, sl_max)

                # 确保止盈空间大于止损空间（至少2:1的比例）
                # 但如果向上空间很小，不要强制2:1，而是基于实际市场空间
                min_tp_ratio = 2.0  # 止盈至少是止损的2倍
                if tp_percent < sl_percent * min_tp_ratio:
                    # 如果向上空间足够，可以设置2:1比例
                    if upward_space >= sl_percent * min_tp_ratio:
                        tp_percent = sl_percent * min_tp_ratio
                        tp_percent = min(tp_percent, tp_max)
                    else:
                        # 如果向上空间不足，使用实际向上空间的80%作为TP，但至少是SL的1.5倍
                        tp_percent = max(upward_space * 0.8, sl_percent * 1.5)
                        tp_percent = min(tp_percent, tp_max)

            else:  # SHORT
                # 做空：止盈在下方，止损在上方
                tp_candidate1 = downward_space * 0.6 if downward_space > 0 else 0
                tp_candidate2 = atr_15m_percent * 3.0 if atr_15m_percent > 0 else 0
                tp_min = 3.0
                tp_max = 10.0 if is_counter_trend else 8.0
                
                # 如果向下空间很小（<2%），限制最大TP为向下空间的80%
                if downward_space > 0 and downward_space < 2.0:
                    tp_max = min(tp_max, downward_space * 0.8)
                    tp_min = min(tp_min, downward_space * 0.5)
                
                tp_percent = max(tp_candidate1, tp_candidate2, tp_min)
                tp_percent = min(tp_percent, tp_max)

                sl_candidate1 = upward_space * 0.5 if upward_space > 0 else 0
                sl_candidate2 = atr_15m_percent * 2.0 if atr_15m_percent > 0 else 0
                sl_min = 3.0 if is_counter_trend else 2.0
                sl_max = 6.0 if is_counter_trend else 5.0
                sl_percent = max(sl_candidate1, sl_candidate2, sl_min)
                sl_percent = min(sl_percent, sl_max)

                min_tp_ratio = 2.0
                if tp_percent < sl_percent * min_tp_ratio:
                    # 如果向下空间足够，可以设置2:1比例
                    if downward_space >= sl_percent * min_tp_ratio:
                        tp_percent = sl_percent * min_tp_ratio
                        tp_percent = min(tp_percent, tp_max)
                    else:
                        # 如果向下空间不足，使用实际向下空间的80%作为TP，但至少是SL的1.5倍
                        tp_percent = max(downward_space * 0.8, sl_percent * 1.5)
                        tp_percent = min(tp_percent, tp_max)

            trade_logger.info(
                f"止盈止损计算(15m周期) | {direction} | 向上空间={upward_space:.2f}% | 向下空间={downward_space:.2f}% | 15m_ATR={atr_15m_percent:.2f}% | TP={tp_percent:.2f}% | SL={sl_percent:.2f}%"
            )

            return {
                "tp_percent": round(tp_percent, 2),
                "sl_percent": round(sl_percent, 2)
            }
        except Exception as e:
            trade_logger.warning(f"计算止盈止损失败: {e}")
            return {"tp_percent": 4.0, "sl_percent": 2.5}

    async def _push_to_trade_queue(self, trade_json: Dict) -> bool:
        """推送交易订单到 Redis 队列"""
        try:
            r = redis.Redis(
                host=self.trade_redis_config['host'],
                port=self.trade_redis_config['port'],
                password=self.trade_redis_config['password'],
                db=self.trade_redis_config['db'],
                decode_responses=self.trade_redis_config['decode_responses'],
                socket_connect_timeout=10,
                socket_timeout=10)

            json_str = json.dumps(trade_json, ensure_ascii=False)
            result = r.lpush(self.trade_queue_name, json_str)
            r.close()
            # 成功信息由调用方记录
            return True
        except Exception as e:
            trade_logger.error(f"推送交易订单失败: {e}")
            return False

    def _get_symbol_step_size(self, symbol: str) -> float:
        """获取交易对的步长（stepSize）"""
        # 常见交易对的 stepSize 映射
        precision_map = {
            "BTCUSDT": 0.001,
            "ETHUSDT": 0.001,
            "BNBUSDT": 0.001,
            "SOLUSDT": 0.01,
            "ADAUSDT": 0.1,
            "DOGEUSDT": 1.0,
            "BEATUSDT": 1.0,
            "WIFUSDT": 1.0,
            "POLUSDT": 1.0,
            "TRADOORUSDT": 1.0,
            "VVVUSDT": 1.0,
            "PLAYUSDT": 1.0,
        }
        return precision_map.get(symbol, 1.0)  # 默认 1.0

    def _format_quantity(self, quantity: any, symbol: str, order_type: str,
                         price: float) -> str:
        """格式化交易数量，符合币安精度要求"""
        try:
            from decimal import Decimal, ROUND_DOWN, ROUND_UP

            step_size = self._get_symbol_step_size(symbol)
            MIN_NOTIONAL = 5.0

            # 转换为 Decimal
            if isinstance(quantity, str):
                quantity_decimal = Decimal(quantity)
            else:
                quantity_decimal = Decimal(str(float(quantity)))

            step_decimal = Decimal(str(step_size))
            step_str = str(step_size)
            decimal_places = len(
                step_str.split('.')[-1].rstrip('0')) if '.' in step_str else 0

            # 开仓向下取整，平仓向上取整
            rounding = ROUND_DOWN if order_type == "open" else ROUND_UP
            quantize_exp = Decimal('0.' + '0' * (decimal_places - 1) +
                                   '1') if decimal_places > 0 else Decimal('1')
            rounded_quantity = quantity_decimal.quantize(quantize_exp,
                                                         rounding=rounding)

            # 对齐到 stepSize（对于所有 stepSize 都需要对齐）
            rounded_quantity = (rounded_quantity //
                                step_decimal) * step_decimal
            rounded_quantity = rounded_quantity.quantize(quantize_exp,
                                                         rounding=rounding)

            # 确保数量 > 0
            if rounded_quantity <= 0:
                rounded_quantity = step_decimal
                rounded_quantity = rounded_quantity.quantize(quantize_exp,
                                                             rounding=ROUND_UP)

            # 检查最小名义价值（5 USDT）
            if price > 0:
                notional_value = float(rounded_quantity) * price
                if notional_value < MIN_NOTIONAL:
                    min_quantity = Decimal(str(MIN_NOTIONAL / price))
                    min_quantity = (min_quantity // step_decimal +
                                    Decimal('1')) * step_decimal
                    min_quantity = min_quantity.quantize(quantize_exp,
                                                         rounding=ROUND_UP)
                    rounded_quantity = min_quantity

            # 格式化输出字符串
            result_str = str(rounded_quantity)
            if decimal_places == 0:
                # 整数，去掉小数点
                if '.' in result_str:
                    result_str = result_str.split('.')[0]
                return result_str

            # 小数，保留指定精度
            if '.' in result_str:
                parts = result_str.split('.')
                integer_part = parts[0]
                decimal_part = parts[1].rstrip('0')
                if len(decimal_part) == 0 and decimal_places > 0:
                    decimal_part = '0' * decimal_places
                elif len(decimal_part) < decimal_places:
                    decimal_part = decimal_part + '0' * (decimal_places -
                                                         len(decimal_part))
                result_str = f"{integer_part}.{decimal_part}" if decimal_part else integer_part
            else:
                if decimal_places > 0:
                    result_str = result_str + '.' + '0' * decimal_places

            return result_str
        except Exception as e:
            trade_logger.error(f"格式化数量失败: {e}, 使用原始值")
            # 如果格式化失败，至少确保是字符串且去掉多余小数
            if isinstance(quantity, (int, float)):
                return str(
                    int(quantity)
                ) if step_size >= 1.0 else f"{float(quantity):.{len(str(step_size).split('.')[-1].rstrip('0'))}f}".rstrip(
                    '0').rstrip('.')
            return str(quantity)

    def _build_trade_json(self,
                          decision: Dict,
                          event_data: Dict,
                          mark_price: float,
                          calculated_tp_sl: Dict = None) -> Optional[Dict]:
        """根据决策结果构建交易 JSON"""
        try:
            order_type = decision.get("order_type")
            if not order_type or order_type not in ["open", "close", "reduce"]:
                return None

            symbol = decision.get("symbol")
            position_side = decision.get("position_side")
            side = decision.get("side")
            leverage = decision.get("leverage", 20.0)
            margin = decision.get("margin", 200.0)
            quantity = decision.get("quantity")
            limit_price = decision.get("limit_price", 0.0)
            # 优先使用计算出的止盈止损，如果LLM提供了合理的值则使用LLM的值
            llm_tp = decision.get("tp_trigger_px", 0.0)
            llm_sl = decision.get("sl_trigger_px", 0.0)

            # 如果提供了计算出的止盈止损，且LLM的值不合理（为0或默认值），则使用计算出的值
            if calculated_tp_sl:
                tp_trigger_px = calculated_tp_sl[
                    "tp_percent"] if llm_tp <= 0 or llm_tp == 2.0 else llm_tp
                sl_trigger_px = calculated_tp_sl[
                    "sl_percent"] if llm_sl <= 0 or llm_sl == 1.0 else llm_sl
                trade_logger.info(
                    f"止盈止损设置 | {symbol} | 使用计算值: TP={tp_trigger_px}% SL={sl_trigger_px}% | LLM值: TP={llm_tp} SL={llm_sl}"
                )
            else:
                # 如果没有计算值，使用LLM的值或默认值
                tp_trigger_px = llm_tp if llm_tp > 0 else 2.0
                sl_trigger_px = llm_sl if llm_sl > 0 else 1.0

            trade_trigger_mode = decision.get("trade_trigger_mode", 1)
            order_type_binance = decision.get("order_type_binance", "MARKET")

            # 计算数量（如果未提供）
            raw_quantity = None
            if not quantity or quantity == "0" or quantity == 0:
                if order_type == "open":
                    # 开仓：根据保证金和杠杆计算
                    if mark_price > 0:
                        raw_quantity = margin * leverage / mark_price
                    else:
                        trade_logger.error(f"无法计算数量：mark_price={mark_price}")
                        return None
                else:
                    # 平仓/减仓：需要从持仓获取，这里暂时返回 None
                    trade_logger.warning(f"平仓/减仓需要从持仓获取数量，暂不支持")
                    return None
            else:
                # 使用 LLM 返回的数量
                raw_quantity = quantity

            # 格式化数量（符合币安精度要求）
            formatted_quantity = self._format_quantity(raw_quantity, symbol,
                                                       order_type, mark_price)
            trade_logger.info(
                f"数量格式化 | {symbol} | 原始={raw_quantity} | 格式化后={formatted_quantity}"
            )

            trade_json = {
                "order_type": order_type,
                "symbol": symbol,
                "positionSide": position_side,
                "side": side,
                "leverage": float(leverage),
                "sums": formatted_quantity,  # 使用格式化后的数量
                "openAvgPx": float(mark_price),
                "task_id": 23,  # 默认值，后续可从配置获取
                "user_id": 2,  # 默认值，后续可从配置获取
                "api_id": 0,  # 默认值，后续可从配置获取
                "trade_trigger_mode": int(trade_trigger_mode),
                "tp_trigger_px": float(tp_trigger_px),
                "sl_trigger_px": float(sl_trigger_px),
                "acc": {
                    "key": "",  # 需要从配置获取
                    "secret": "",  # 需要从配置获取
                    "passphrase": "",
                    "proxies": {},
                    "exchange": 2
                },
                "flag": "1",  # 1=模拟盘，0=实盘
                "uniqueName": "ai_trading_system"
            }

            # 限价单额外字段
            if order_type_binance == "LIMIT" and limit_price > 0:
                trade_json["order_type_binance"] = "LIMIT"
                trade_json["limit_price"] = float(limit_price)
                trade_json["timeInForce"] = "GTC"

            return trade_json
        except Exception as e:
            trade_logger.error(f"构建交易 JSON 失败: {e}")
            return None

    async def execute(self, ctx: StepInput) -> str:
        prev_result = self._parse_step_content(ctx.previous_step_content)

        # 从 step2_result 或 step1_result 中提取数据
        step2_result = prev_result.get("step2_result", {})
        step1_result = step2_result.get("step1_result",
                                        prev_result.get("step1_result", {}))

        # event_data 在 step1_result 中
        event_data = step1_result.get("event_data",
                                      prev_result.get("event_data", {}))
        sv_output = step1_result.get("sv_output",
                                     prev_result.get("sv_output", {}))

        # position_risk 的结果在 step2_result 中
        pr_result = step2_result.get("decisions",
                                     prev_result.get("decisions", []))
        risk_results = step2_result.get("risk_results",
                                        prev_result.get("risk_results", []))

        symbol = event_data.get("symbol")
        exchange = event_data.get("exchange", "binance")
        event_id = event_data.get("event_id", "")

        # 如果 symbol 仍然为 None，尝试从其他位置获取
        if not symbol:
            # 尝试从 step1_result 的 event_data 中获取
            if step1_result.get("event_data", {}).get("symbol"):
                symbol = step1_result["event_data"]["symbol"]
            # 如果还是没有，记录错误
            if not symbol:
                trade_logger.error(
                    f"无法从 event_data 中获取 symbol，prev_result keys: {list(prev_result.keys())}"
                )
                return self._safe_json_dumps({
                    "decision":
                    "NO_ACTION",
                    "reason":
                    "无法获取 symbol",
                    "error":
                    "event_data 中缺少 symbol 字段"
                })

        trade_logger.info(f"=== 交易决策开始 === | {symbol} | {event_id}")

        # 开始推理日志记录
        reasoning_logger.info("=" * 80)
        reasoning_logger.info(
            f"推理开始 | {symbol} | {event_id} | {datetime.now().isoformat()}")
        reasoning_logger.info("=" * 80)

        # 1. 获取当前价格
        mark_price = await get_mark_price_from_redis(exchange, symbol)
        if not mark_price or mark_price <= 0:
            trade_logger.warning(
                f"无法获取当前价格 | {symbol} | event_id={event_id} | key=price:{exchange}:{symbol}"
            )
            reasoning_logger.warning(f"价格数据 | {symbol} | 无法获取当前价格")
            # 即使没有价格，也继续执行（可能后续步骤会处理）
            mark_price = 0.0
        else:
            trade_logger.info(f"当前价格 | {symbol} | {mark_price}")
            reasoning_logger.info(f"价格数据 | {symbol} | mark_price={mark_price}")

        # 2. 获取 L1 事件（优先根据event_id匹配，确保获取的是触发工作流时的事件）
        l1_event = await self._fetch_l1_event(exchange, symbol, event_id)
        if l1_event:
            l1_event_id = l1_event.get("event_id", "")
            l1_score = l1_event.get("total_score", "")
            
            # 验证event_id是否匹配（如果提供了event_id）
            if event_id:
                if l1_event_id != event_id:
                    trade_logger.warning(
                        f"L1事件event_id不匹配 | {symbol} | 期望={event_id} | 实际={l1_event_id} | 将使用实际获取的事件"
                    )
                    reasoning_logger.warning(
                        f"L1事件event_id不匹配 | {symbol} | 期望={event_id} | 实际={l1_event_id}"
                    )
                else:
                    trade_logger.debug(
                        f"L1事件event_id匹配成功 | {symbol} | event_id={event_id}"
                    )
            
            trade_logger.info(
                f"L1事件 | {symbol} | direction={l1_event.get('direction')} | score={l1_score}"
            )
            reasoning_logger.info(
                f"L1事件数据 | {symbol} | {json.dumps(l1_event, ensure_ascii=False)}"
            )
        else:
            trade_logger.warning(
                f"未找到L1事件 | {symbol} | event_id={event_id if event_id else 'N/A'}"
            )
            reasoning_logger.warning(
                f"L1事件数据 | {symbol} | 未找到 | event_id={event_id if event_id else 'N/A'}"
            )

        # 3. 获取市场结构
        market_structure = await self._fetch_market_structure(exchange, symbol)
        if market_structure:
            # 从实际数据结构中提取信息
            participant_summary = market_structure.get(
                "market_participant_summary", {})
            funding_analysis = market_structure.get("funding_analysis", {})
            consistency = market_structure.get("cross_timeframe_consistency",
                                               {})

            overall_bias = participant_summary.get("overall_bias", "unknown")
            funding_bias = funding_analysis.get("bias", "unknown")
            alignment = consistency.get("sentiment_alignment", "unknown")

            trade_logger.info(
                f"市场结构 | {symbol} | overall_bias={overall_bias} | funding_bias={funding_bias} | alignment={alignment}"
            )
            reasoning_logger.info(
                f"市场结构数据 | {symbol} | overall_bias={overall_bias} | funding_bias={funding_bias} | alignment={alignment}"
            )
            # 记录完整的市场结构（简化版，避免日志过长）
            market_structure_summary = {
                "overall_bias": overall_bias,
                "funding_bias": funding_bias,
                "alignment": alignment
            }
            reasoning_logger.info(
                f"市场结构详情 | {symbol} | {json.dumps(market_structure_summary, ensure_ascii=False)}"
            )
        else:
            trade_logger.warning(f"未找到market_structure | {symbol}")
            reasoning_logger.warning(f"市场结构数据 | {symbol} | 未找到")

        # 3.5. 获取K线数据（用于趋势判断和止盈止损计算）
        klines_5m = await self._fetch_klines(exchange, symbol, "5m")
        klines_15m = await self._fetch_klines(exchange, symbol, "15m")
        klines_30m = await self._fetch_klines(exchange, symbol, "30m")
        if klines_5m:
            trade_logger.info(f"获取到5m K线数据 | {symbol} | 数量={len(klines_5m)}")
        if klines_15m:
            trade_logger.info(f"获取到15m K线数据 | {symbol} | 数量={len(klines_15m)}")
        if klines_30m:
            trade_logger.info(f"获取到30m K线数据 | {symbol} | 数量={len(klines_30m)}")

        # 4. 获取当前持仓（从 position_risk 结果中提取）
        positions = []
        if pr_result:
            for decision in pr_result:
                trade_id = decision.get("trade_id")
                if trade_id:
                    positions.append({
                        "trade_id": trade_id,
                        "position_side": decision.get("side"),
                        "decision": decision.get("decision")
                    })

        # 5. 构建查询
        agent_output = sv_output.get("agent_output", sv_output)
        verdict = agent_output.get("verdict", "UNKNOWN")
        direction = agent_output.get("direction", "neutral")

        trade_logger.info(
            f"信号验证结果 | {symbol} | verdict={verdict} | direction={direction}")

        # 提取风控建议（取第一个持仓的风控结果，如果没有持仓则取第一个风险结果）
        risk_advice = {}
        if risk_results:
            risk_advice = risk_results[0].get("payload", risk_results[0])
        else:
            risk_advice = {"risk_state": "LOW", "recommended_action": "HOLD"}

        trade_logger.info(
            f"风控建议 | {symbol} | risk_state={risk_advice.get('risk_state')} | action={risk_advice.get('recommended_action')}"
        )

        # 5.1. 分析15m和30m趋势（用于判断大趋势方向）
        # 获取市场结构用于趋势验证
        market_structure_data = None
        try:
            market_structure_key = f"background:binance:{symbol}:market_structure"
            rc = RedisClient()
            market_structure_str = await rc.client.get(market_structure_key)
            if market_structure_str:
                market_structure_data = json.loads(
                    market_structure_str) if isinstance(
                        market_structure_str, str) else market_structure_str
        except Exception as e:
            trade_logger.debug(f"获取市场结构失败 | {symbol} | {e}")

        trend_analysis = self._analyze_trend_from_klines(
            klines_15m, klines_30m, mark_price, market_structure_data)
        trade_logger.info(
            f"趋势分析 | {symbol} | 15m+30m趋势={trend_analysis.get('trend')} | 强度={trend_analysis.get('strength')} | 置信度={trend_analysis.get('confidence')}"
        )
        reasoning_logger.info(
            f"趋势分析结果 | {symbol} | {json.dumps(trend_analysis, ensure_ascii=False)}"
        )
        reasoning_logger.info(
            f"K线数据统计 | {symbol} | 5m={len(klines_5m)}根 | 15m={len(klines_15m)}根 | 30m={len(klines_30m)}根"
        )

        query = {
            "symbol": symbol,
            "exchange": exchange,
            "event_id": event_data.get("event_id"),
            "ts_now": int(time.time() * 1000),
            "mark_price": mark_price,
            "signal_validation": {
                "verdict":
                verdict,
                "direction":
                direction,
                "confidence_adjustment":
                agent_output.get("confidence_adjustment", "none")
            },
            "position_risk": {
                "risk_state": risk_advice.get("risk_state", "LOW"),
                "recommended_action": risk_advice.get("recommended_action",
                                                      "HOLD"),
                "reduce_pct": risk_advice.get("reduce_pct", 0.0),
                "add_pct": risk_advice.get("add_pct", 0.0)
            },
            "l1_event": l1_event or {},
            "market_structure": market_structure or {},
            "trend_analysis": trend_analysis,  # 添加趋势分析结果
            "positions": positions,
            "default_margin": 200.0,  # 默认保证金 200U
            "default_leverage": 20.0  # 默认杠杆 20倍
        }

        # 6. 调用 TradeDecisionExpert
        trade_logger.info(f"调用TradeDecisionExpert | {symbol} | {event_id}")

        # 记录LLM查询内容
        query_str = json.dumps(query, ensure_ascii=False, indent=2)
        reasoning_logger.info(f"LLM查询输入 | {symbol} | {event_id}")
        reasoning_logger.info(f"查询内容:\n{query_str}")

        try:
            import asyncio
            # 设置超时：60秒
            td_output_str = await asyncio.wait_for(self.expert.run(
                json.dumps(query, ensure_ascii=False)),
                                                   timeout=60.0)
            reasoning_logger.info(
                f"LLM响应 | {symbol} | {event_id} | 响应长度={len(td_output_str)}")
            reasoning_logger.info(
                f"LLM原始响应:\n{td_output_str[:2000]}")  # 限制长度避免日志过长
        except asyncio.TimeoutError:
            trade_logger.error(
                f"TradeDecisionExpert 调用超时 | {symbol} | {event_id}")
            reasoning_logger.error(
                f"LLM调用异常 | {symbol} | {event_id} | 超时（60秒）")
            td_output = {
                "decision": "NO_ACTION",
                "should_execute": False,
                "error": "LLM调用超时",
                "reasoning": ["TradeDecisionExpert调用超时（60秒）"]
            }
        except Exception as e:
            trade_logger.error(
                f"TradeDecisionExpert 调用失败 | {symbol} | {event_id} | {e}")
            reasoning_logger.error(f"LLM调用异常 | {symbol} | {event_id} | 错误={e}")
            td_output = {
                "decision": "NO_ACTION",
                "should_execute": False,
                "error": f"LLM调用失败: {str(e)}",
                "reasoning": [f"TradeDecisionExpert异常: {str(e)}"]
            }
        else:
            # 解析输出
            try:
                td_output = json.loads(td_output_str)
                # 如果解析后是 {"raw": "..."}，尝试从 raw 中提取 JSON
                if isinstance(td_output,
                              dict) and "raw" in td_output and isinstance(
                                  td_output["raw"], str):
                    from agent_server.agents.experts.utils import _extract_json_from_text
                    extracted = _extract_json_from_text(td_output["raw"])
                    if extracted:
                        td_output = extracted
                        reasoning_logger.info(
                            f"LLM输出解析 | {symbol} | 从raw字段提取JSON成功")
                    else:
                        reasoning_logger.warning(
                            f"LLM输出解析 | {symbol} | 从raw字段提取JSON失败")
            except json.JSONDecodeError:
                # 如果直接解析失败，尝试提取 JSON
                reasoning_logger.warning(f"LLM输出解析 | {symbol} | JSON解析失败，尝试提取")
                from agent_server.agents.experts.utils import _extract_json_from_text
                extracted = _extract_json_from_text(td_output_str)
                if extracted:
                    td_output = extracted
                    reasoning_logger.info(f"LLM输出解析 | {symbol} | 提取JSON成功")
                else:
                    td_output = {
                        "raw": td_output_str,
                        "decision": "NO_ACTION",
                        "should_execute": False
                    }
                    reasoning_logger.warning(
                        f"LLM输出解析 | {symbol} | 提取JSON失败，使用默认值")
            except Exception as e:
                trade_logger.warning(
                    f"解析 TradeDecisionExpert 输出失败 | {symbol} | {e}")
                reasoning_logger.error(f"LLM输出解析异常 | {symbol} | 错误={e}")
                td_output = {
                    "raw": td_output_str,
                    "decision": "NO_ACTION",
                    "should_execute": False
                }

            # 记录解析后的决策结果
            reasoning_logger.info(
                f"LLM决策结果 | {symbol} | {json.dumps(td_output, ensure_ascii=False, indent=2)}"
            )

        decision = td_output.get("decision", "NO_ACTION")
        should_execute = td_output.get("should_execute", False)
        confidence = td_output.get("confidence", 0.0)

        trade_logger.info(
            f"交易决策结果 | {symbol} | decision={decision} | should_execute={should_execute} | confidence={confidence}"
        )

        if "reasoning" in td_output:
            trade_logger.info(
                f"决策理由 | {symbol} | {json.dumps(td_output.get('reasoning'), ensure_ascii=False)}"
            )

        # 6.5. 验证开仓方向是否与趋势一致（代码层面二次验证 - 放宽限制）
        if should_execute and decision in ["OPEN_LONG", "OPEN_SHORT"]:
            trend = trend_analysis.get("trend", "neutral")
            strength = trend_analysis.get("strength", "weak")
            l1_score = abs(float(l1_event.get("total_score",
                                              0))) if l1_event else 0

            reasoning_logger.info(
                f"趋势验证 | {symbol} | LLM决策={decision} | 趋势={trend} | 强度={strength} | L1分数={l1_score}"
            )

            # 严格趋势验证：strong趋势时，完全禁止逆势交易（除非L1信号极端强烈>=60）
            # 这是为了避免逆势交易导致亏损
            if trend == "bullish" and strength == "strong" and decision == "OPEN_SHORT":
                if l1_score < 60:  # 只有极端强烈的L1信号(>=60)才允许逆势
                    trade_logger.warning(
                        f"趋势冲突 | {symbol} | 趋势=bullish(strong)但决策=OPEN_SHORT，禁止逆势交易（L1信号={l1_score}）"
                    )
                    reasoning_logger.warning(
                        f"趋势冲突检测 | {symbol} | 趋势=bullish(strong)但决策=OPEN_SHORT，禁止逆势交易（L1信号={l1_score}）"
                    )
                    decision = "NO_ACTION"
                    should_execute = False
                    td_output["decision"] = "NO_ACTION"
                    td_output["should_execute"] = False
                    td_output[
                        "reason"] = f"趋势分析显示bullish(strong)，禁止逆势做空（L1信号={l1_score}，需要>=60才允许逆势）"
                else:
                    reasoning_logger.warning(
                        f"趋势冲突但允许 | {symbol} | 趋势=bullish(strong)但L1信号极端强烈({l1_score})，允许逆势做空但风险极高"
                    )
            elif trend == "bearish" and strength == "strong" and decision == "OPEN_LONG":
                if l1_score < 60:  # 只有极端强烈的L1信号(>=60)才允许逆势
                    trade_logger.warning(
                        f"趋势冲突 | {symbol} | 趋势=bearish(strong)但决策=OPEN_LONG，禁止逆势交易（L1信号={l1_score}）"
                    )
                    reasoning_logger.warning(
                        f"趋势冲突检测 | {symbol} | 趋势=bearish(strong)但决策=OPEN_LONG，禁止逆势交易（L1信号={l1_score}）"
                    )
                    decision = "NO_ACTION"
                    should_execute = False
                    td_output["decision"] = "NO_ACTION"
                    td_output["should_execute"] = False
                    td_output[
                        "reason"] = f"趋势分析显示bearish(strong)，禁止逆势做多（L1信号={l1_score}，需要>=60才允许逆势）"
                else:
                    reasoning_logger.warning(
                        f"趋势冲突但允许 | {symbol} | 趋势=bearish(strong)但L1信号极端强烈({l1_score})，允许逆势做多但风险极高"
                    )
            else:
                if trend != "neutral" and strength in ["strong", "moderate"]:
                    # 趋势与决策一致，记录
                    if (trend == "bullish" and decision == "OPEN_LONG") or (
                            trend == "bearish" and decision == "OPEN_SHORT"):
                        reasoning_logger.info(
                            f"趋势验证通过 | {symbol} | 决策={decision} | 趋势={trend}({strength}) | 方向一致"
                        )
                    else:
                        reasoning_logger.info(
                            f"趋势验证通过 | {symbol} | 决策={decision} | 趋势={trend}({strength}) | 方向冲突但L1信号足够强({l1_score})，允许开仓"
                        )
                else:
                    reasoning_logger.info(
                        f"趋势验证通过 | {symbol} | 决策={decision} | 趋势={trend}({strength}) | 趋势不明确，基于L1信号决策"
                    )

        # 7. 如果 should_execute==true，推送到交易队列
        calculated_tp_sl = None  # 初始化变量
        if should_execute and decision in [
                "OPEN_LONG", "OPEN_SHORT", "CLOSE", "REDUCE"
        ]:
            reasoning_logger.info(
                f"执行交易准备 | {symbol} | decision={decision} | should_execute={should_execute}"
            )

            # 检查是否逆势交易
            is_counter_trend = False
            if trend_analysis:
                trend = trend_analysis.get("trend", "neutral")
                strength = trend_analysis.get("strength", "weak")
                if strength == "strong":
                    if (trend == "bullish" and decision == "OPEN_SHORT") or (
                            trend == "bearish" and decision == "OPEN_LONG"):
                        is_counter_trend = True
                        reasoning_logger.warning(
                            f"逆势交易检测 | {symbol} | 决策={decision} | 趋势={trend}({strength}) | 将使用更大的止损空间"
                        )

            # 根据5m K线数据计算合理的止盈止损（考虑趋势和支撑阻力）
            calculated_tp_sl = self._calculate_tp_sl_from_klines(
                klines_5m, klines_15m, klines_30m, mark_price,
                "LONG" if decision in ["OPEN_LONG"] else "SHORT",
                trend_analysis, is_counter_trend)
            trade_logger.info(
                f"计算止盈止损 | {symbol} | 15m数据={len(klines_15m)}根 | TP={calculated_tp_sl['tp_percent']}% | SL={calculated_tp_sl['sl_percent']}%"
            )
            reasoning_logger.info(
                f"止盈止损计算 | {symbol} | {json.dumps(calculated_tp_sl, ensure_ascii=False)}"
            )

            trade_json = self._build_trade_json(td_output, event_data,
                                                mark_price, calculated_tp_sl)
            if trade_json:
                reasoning_logger.info(
                    f"交易JSON构建 | {symbol} | {json.dumps(trade_json, ensure_ascii=False, indent=2)}"
                )

                success = await self._push_to_trade_queue(trade_json)
                td_output["trade_pushed"] = success
                td_output["trade_json"] = trade_json

                if success:
                    trade_logger.info(
                        f"交易订单已推送 | {symbol} | {decision} | quantity={trade_json.get('sums')} | price={trade_json.get('openAvgPx')}"
                    )
                    reasoning_logger.info(
                        f"交易推送成功 | {symbol} | {decision} | quantity={trade_json.get('sums')} | price={trade_json.get('openAvgPx')} | TP={trade_json.get('tp_trigger_px')}% | SL={trade_json.get('sl_trigger_px')}%"
                    )
                else:
                    trade_logger.error(f"交易订单推送失败 | {symbol} | {decision}")
                    reasoning_logger.error(f"交易推送失败 | {symbol} | {decision}")
            else:
                td_output["trade_pushed"] = False
                td_output["error"] = "无法构建交易 JSON"
                trade_logger.error(f"无法构建交易JSON | {symbol} | {decision}")
                reasoning_logger.error(f"交易JSON构建失败 | {symbol} | {decision}")
        else:
            td_output["trade_pushed"] = False
            td_output[
                "reason"] = f"should_execute={should_execute}, decision={decision}"
            trade_logger.info(
                f"不执行交易 | {symbol} | reason={td_output.get('reason')}")
            reasoning_logger.info(
                f"不执行交易 | {symbol} | reason={td_output.get('reason')}")

        # 记录完整决策过程到 Redis
        await self._save_decision_to_redis(symbol, event_id, td_output, query)

        # 记录最终推理结果摘要
        final_summary = {
            "symbol": symbol,
            "event_id": event_id,
            "decision": decision,
            "should_execute": should_execute,
            "confidence": confidence,
            "trend_analysis": trend_analysis,
            "calculated_tp_sl": calculated_tp_sl,
            "trade_pushed": td_output.get("trade_pushed", False),
            "reasoning": td_output.get("reasoning", [])
        }
        reasoning_logger.info(
            f"推理结果摘要 | {symbol} | {json.dumps(final_summary, ensure_ascii=False, indent=2)}"
        )
        reasoning_logger.info("=" * 80)
        reasoning_logger.info(
            f"推理完成 | {symbol} | {event_id} | decision={decision}")
        reasoning_logger.info("=" * 80)
        reasoning_logger.info("")  # 空行分隔

        trade_logger.info(
            f"=== 交易决策完成 === | {symbol} | {event_id} | decision={decision}")

        return self._safe_json_dumps({
            "trade_decision": td_output,
            "step2_result": prev_result
        })

    async def _save_decision_to_redis(self, symbol: str, event_id: str,
                                      decision: dict, query: dict):
        """将决策过程保存到 Redis"""
        try:
            rc = RedisClient()
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "event_id": event_id,
                "query": query,
                "decision": decision
            }
            key = f"trade:decision:{symbol}:{datetime.now().strftime('%Y%m%d')}"
            await rc.client.lpush(key, json.dumps(log_data,
                                                  ensure_ascii=False))
            await rc.client.ltrim(key, 0, 999)  # 只保留最近 1000 条
            await rc.client.expire(key, 86400 * 7)  # 7 天过期
        except Exception as e:
            trade_logger.error(f"保存决策到Redis失败 | {symbol} | {e}")
