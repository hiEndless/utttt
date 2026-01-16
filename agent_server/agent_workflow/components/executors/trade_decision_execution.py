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

    async def _fetch_l1_event(self, exchange: str, symbol: str) -> Optional[Dict]:
        """从 l1_events stream 读取最新的 L1 事件"""
        try:
            rc = RedisClient()
            # 从 l1_events stream 读取最新事件
            stream_key = "l1_events"
            res = await rc.client.xrevrange(stream_key, max="+", min="-", count=20)
            
            if not res:
                return None
            
            # 查找匹配 symbol 的事件
            for entry_id, fields in res:
                event = {}
                for k, v in fields.items():
                    key = k.decode() if isinstance(k, bytes) else k
                    val = v.decode() if isinstance(v, bytes) else v
                    event[key] = val
                
                # 检查是否匹配（检查 symbol 字段）
                event_symbol = event.get("symbol", "")
                if event_symbol == symbol:
                    # 解析 payload 如果存在
                    if "payload" in event and isinstance(event["payload"], str):
                        try:
                            event["payload"] = json.loads(event["payload"])
                        except:
                            pass
                    return event
            
            return None
        except Exception as e:
            trade_logger.debug(f"读取 L1 事件失败: {e}")
            return None

    async def _fetch_market_structure(self, exchange: str, symbol: str) -> Optional[Dict]:
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
                            trade_logger.debug(f"从 DB {db} 读取到 market_structure | {symbol}")
                        return result
                    except json.JSONDecodeError as e:
                        trade_logger.warning(f"解析 market_structure JSON 失败 | {symbol} | DB {db} | {e}")
                        continue
            except Exception as e:
                trade_logger.debug(f"从 DB {db} 读取 market_structure 失败 | {symbol} | {e}")
                continue
        
        trade_logger.warning(f"未找到 market_structure | {symbol} | 已尝试 DB: {db_candidates}")
        return None

    async def _fetch_klines(self, exchange: str, symbol: str, interval: str) -> List:
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
                                trade_logger.debug(f"从 DB {db} 读取到 {interval} K线 | {symbol} | 数量={len(result)}")
                            return result
                    except json.JSONDecodeError as e:
                        trade_logger.debug(f"解析 {interval} K线 JSON 失败 | {symbol} | DB {db} | {e}")
                        continue
            except Exception as e:
                trade_logger.debug(f"从 DB {db} 读取 {interval} K线失败 | {symbol} | {e}")
                continue
        
        return []

    def _calculate_tp_sl_from_klines(self, klines_5m: List, klines_15m: List, current_price: float, direction: str) -> Dict[str, float]:
        """
        根据5m和15m K线数据计算合理的止盈止损百分比（使用ATR类似的方法）
        
        Args:
            klines_5m: 5分钟K线数据列表，格式: [[timestamp, open, high, low, close, volume], ...]
            klines_15m: 15分钟K线数据列表
            current_price: 当前价格
            direction: 交易方向 "LONG" 或 "SHORT"
        
        Returns:
            {"tp_percent": float, "sl_percent": float}
        """
        try:
            # 默认值（如果无法计算）
            default_tp = 1.5  # 1.5%
            default_sl = 0.8   # 0.8%
            
            if not klines_5m and not klines_15m:
                return {"tp_percent": default_tp, "sl_percent": default_sl}
            
            # 计算5m周期的ATR（平均真实波幅）- 使用最近14根K线
            atr_5m = 0.0
            if klines_5m and len(klines_5m) >= 2:
                recent_5m = klines_5m[-14:] if len(klines_5m) > 14 else klines_5m
                true_ranges = []
                for i in range(1, len(recent_5m)):
                    prev_close = float(recent_5m[i-1][4]) if len(recent_5m[i-1]) > 4 else current_price
                    high = float(recent_5m[i][2]) if len(recent_5m[i]) > 2 else current_price
                    low = float(recent_5m[i][3]) if len(recent_5m[i]) > 3 else current_price
                    tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                    true_ranges.append(tr)
                if true_ranges:
                    atr_5m = sum(true_ranges) / len(true_ranges)
                    atr_5m_percent = (atr_5m / current_price) * 100 if current_price > 0 else 0
                else:
                    atr_5m_percent = 0.0
            else:
                atr_5m_percent = 0.0
            
            # 计算15m周期的ATR（使用最近10根K线）
            atr_15m = 0.0
            if klines_15m and len(klines_15m) >= 2:
                recent_15m = klines_15m[-10:] if len(klines_15m) > 10 else klines_15m
                true_ranges = []
                for i in range(1, len(recent_15m)):
                    prev_close = float(recent_15m[i-1][4]) if len(recent_15m[i-1]) > 4 else current_price
                    high = float(recent_15m[i][2]) if len(recent_15m[i]) > 2 else current_price
                    low = float(recent_15m[i][3]) if len(recent_15m[i]) > 3 else current_price
                    tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                    true_ranges.append(tr)
                if true_ranges:
                    atr_15m = sum(true_ranges) / len(true_ranges)
                    atr_15m_percent = (atr_15m / current_price) * 100 if current_price > 0 else 0
                else:
                    atr_15m_percent = 0.0
            else:
                atr_15m_percent = 0.0
            
            # 使用较大的ATR作为参考（更准确反映波动）
            avg_atr = max(atr_5m_percent, atr_15m_percent) if atr_5m_percent > 0 or atr_15m_percent > 0 else 0
            
            # 根据ATR计算止盈止损（更合理的比例）
            if avg_atr > 0:
                # 止盈：2-3倍ATR（但不超过3%）
                tp_percent = min(avg_atr * 2.5, 3.0)
                # 止损：1-1.5倍ATR（但不超过1.5%）
                sl_percent = min(avg_atr * 1.2, 1.5)
                
                # 确保最小值
                tp_percent = max(tp_percent, 0.8)  # 至少0.8%
                sl_percent = max(sl_percent, 0.5)  # 至少0.5%
            else:
                # 如果无法计算ATR，使用默认值
                tp_percent = default_tp
                sl_percent = default_sl
            
            trade_logger.info(f"ATR计算 | 5m_ATR={atr_5m_percent:.2f}% | 15m_ATR={atr_15m_percent:.2f}% | 使用={avg_atr:.2f}% | TP={tp_percent:.2f}% | SL={sl_percent:.2f}%")
            
            return {
                "tp_percent": round(tp_percent, 2),
                "sl_percent": round(sl_percent, 2)
            }
        except Exception as e:
            trade_logger.warning(f"计算止盈止损失败: {e}")
            return {"tp_percent": 1.5, "sl_percent": 0.8}

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
                socket_timeout=10
            )
            
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
            "BTCUSDT": 0.001, "ETHUSDT": 0.001, "BNBUSDT": 0.001,
            "SOLUSDT": 0.01, "ADAUSDT": 0.1, "DOGEUSDT": 1.0,
            "BEATUSDT": 1.0, "WIFUSDT": 1.0, "POLUSDT": 1.0,
            "TRADOORUSDT": 1.0, "VVVUSDT": 1.0, "PLAYUSDT": 1.0,
        }
        return precision_map.get(symbol, 1.0)  # 默认 1.0

    def _format_quantity(self, quantity: any, symbol: str, order_type: str, price: float) -> str:
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
            decimal_places = len(step_str.split('.')[-1].rstrip('0')) if '.' in step_str else 0
            
            # 开仓向下取整，平仓向上取整
            rounding = ROUND_DOWN if order_type == "open" else ROUND_UP
            quantize_exp = Decimal('0.' + '0' * (decimal_places - 1) + '1') if decimal_places > 0 else Decimal('1')
            rounded_quantity = quantity_decimal.quantize(quantize_exp, rounding=rounding)
            
            # 对齐到 stepSize（对于所有 stepSize 都需要对齐）
            rounded_quantity = (rounded_quantity // step_decimal) * step_decimal
            rounded_quantity = rounded_quantity.quantize(quantize_exp, rounding=rounding)
            
            # 确保数量 > 0
            if rounded_quantity <= 0:
                rounded_quantity = step_decimal
                rounded_quantity = rounded_quantity.quantize(quantize_exp, rounding=ROUND_UP)
            
            # 检查最小名义价值（5 USDT）
            if price > 0:
                notional_value = float(rounded_quantity) * price
                if notional_value < MIN_NOTIONAL:
                    min_quantity = Decimal(str(MIN_NOTIONAL / price))
                    min_quantity = (min_quantity // step_decimal + Decimal('1')) * step_decimal
                    min_quantity = min_quantity.quantize(quantize_exp, rounding=ROUND_UP)
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
                    decimal_part = decimal_part + '0' * (decimal_places - len(decimal_part))
                result_str = f"{integer_part}.{decimal_part}" if decimal_part else integer_part
            else:
                if decimal_places > 0:
                    result_str = result_str + '.' + '0' * decimal_places
            
            return result_str
        except Exception as e:
            trade_logger.error(f"格式化数量失败: {e}, 使用原始值")
            # 如果格式化失败，至少确保是字符串且去掉多余小数
            if isinstance(quantity, (int, float)):
                return str(int(quantity)) if step_size >= 1.0 else f"{float(quantity):.{len(str(step_size).split('.')[-1].rstrip('0'))}f}".rstrip('0').rstrip('.')
            return str(quantity)

    def _build_trade_json(self, decision: Dict, event_data: Dict, mark_price: float, calculated_tp_sl: Dict = None) -> Optional[Dict]:
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
                tp_trigger_px = calculated_tp_sl["tp_percent"] if llm_tp <= 0 or llm_tp == 2.0 else llm_tp
                sl_trigger_px = calculated_tp_sl["sl_percent"] if llm_sl <= 0 or llm_sl == 1.0 else llm_sl
                trade_logger.info(f"止盈止损设置 | {symbol} | 使用计算值: TP={tp_trigger_px}% SL={sl_trigger_px}% | LLM值: TP={llm_tp} SL={llm_sl}")
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
            formatted_quantity = self._format_quantity(raw_quantity, symbol, order_type, mark_price)
            trade_logger.info(f"数量格式化 | {symbol} | 原始={raw_quantity} | 格式化后={formatted_quantity}")
            
            trade_json = {
                "order_type": order_type,
                "symbol": symbol,
                "positionSide": position_side,
                "side": side,
                "leverage": float(leverage),
                "sums": formatted_quantity,  # 使用格式化后的数量
                "openAvgPx": float(mark_price),
                "task_id": 23,  # 默认值，后续可从配置获取
                "user_id": 2,   # 默认值，后续可从配置获取
                "api_id": 0,    # 默认值，后续可从配置获取
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
        step1_result = step2_result.get("step1_result", prev_result.get("step1_result", {}))
        
        # event_data 在 step1_result 中
        event_data = step1_result.get("event_data", prev_result.get("event_data", {}))
        sv_output = step1_result.get("sv_output", prev_result.get("sv_output", {}))
        
        # position_risk 的结果在 step2_result 中
        pr_result = step2_result.get("decisions", prev_result.get("decisions", []))
        risk_results = step2_result.get("risk_results", prev_result.get("risk_results", []))

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
                trade_logger.error(f"无法从 event_data 中获取 symbol，prev_result keys: {list(prev_result.keys())}")
                return self._safe_json_dumps({
                    "decision": "NO_ACTION",
                    "reason": "无法获取 symbol",
                    "error": "event_data 中缺少 symbol 字段"
                })
        
        trade_logger.info(f"=== 交易决策开始 === | {symbol} | {event_id}")
        
        # 1. 获取当前价格
        mark_price = await get_mark_price_from_redis(exchange, symbol)
        if not mark_price or mark_price <= 0:
            trade_logger.warning(f"无法获取当前价格 | {symbol} | event_id={event_id} | key=price:{exchange}:{symbol}")
            # 即使没有价格，也继续执行（可能后续步骤会处理）
            mark_price = 0.0
        else:
            trade_logger.info(f"当前价格 | {symbol} | {mark_price}")

        # 2. 获取 L1 事件
        l1_event = await self._fetch_l1_event(exchange, symbol)
        if l1_event:
            trade_logger.info(f"L1事件 | {symbol} | direction={l1_event.get('direction')} | score={l1_event.get('total_score')}")
        else:
            trade_logger.warning(f"未找到L1事件 | {symbol}")

        # 3. 获取市场结构
        market_structure = await self._fetch_market_structure(exchange, symbol)
        if market_structure:
            # 从实际数据结构中提取信息
            participant_summary = market_structure.get("market_participant_summary", {})
            funding_analysis = market_structure.get("funding_analysis", {})
            consistency = market_structure.get("cross_timeframe_consistency", {})
            
            overall_bias = participant_summary.get("overall_bias", "unknown")
            funding_bias = funding_analysis.get("bias", "unknown")
            alignment = consistency.get("sentiment_alignment", "unknown")
            
            trade_logger.info(f"市场结构 | {symbol} | overall_bias={overall_bias} | funding_bias={funding_bias} | alignment={alignment}")
        else:
            trade_logger.warning(f"未找到market_structure | {symbol}")

        # 3.5. 获取5m和15m K线数据（用于计算止盈止损）
        klines_5m = await self._fetch_klines(exchange, symbol, "5m")
        klines_15m = await self._fetch_klines(exchange, symbol, "15m")
        if klines_5m:
            trade_logger.info(f"获取到5m K线数据 | {symbol} | 数量={len(klines_5m)}")
        if klines_15m:
            trade_logger.info(f"获取到15m K线数据 | {symbol} | 数量={len(klines_15m)}")

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
        
        trade_logger.info(f"信号验证结果 | {symbol} | verdict={verdict} | direction={direction}")
        
        # 提取风控建议（取第一个持仓的风控结果，如果没有持仓则取第一个风险结果）
        risk_advice = {}
        if risk_results:
            risk_advice = risk_results[0].get("payload", risk_results[0])
        else:
            risk_advice = {
                "risk_state": "LOW",
                "recommended_action": "HOLD"
            }
        
        trade_logger.info(f"风控建议 | {symbol} | risk_state={risk_advice.get('risk_state')} | action={risk_advice.get('recommended_action')}")

        query = {
            "symbol": symbol,
            "exchange": exchange,
            "event_id": event_data.get("event_id"),
            "ts_now": int(time.time() * 1000),
            "mark_price": mark_price,
            "signal_validation": {
                "verdict": verdict,
                "direction": direction,
                "confidence_adjustment": agent_output.get("confidence_adjustment", "none")
            },
            "position_risk": {
                "risk_state": risk_advice.get("risk_state", "LOW"),
                "recommended_action": risk_advice.get("recommended_action", "HOLD"),
                "reduce_pct": risk_advice.get("reduce_pct", 0.0),
                "add_pct": risk_advice.get("add_pct", 0.0)
            },
            "l1_event": l1_event or {},
            "market_structure": market_structure or {},
            "positions": positions,
            "default_margin": 200.0,  # 默认保证金 200U
            "default_leverage": 20.0  # 默认杠杆 20倍
        }

        # 6. 调用 TradeDecisionExpert
        trade_logger.info(f"调用TradeDecisionExpert | {symbol} | {event_id}")
        
        try:
            import asyncio
            # 设置超时：60秒
            td_output_str = await asyncio.wait_for(
                self.expert.run(json.dumps(query, ensure_ascii=False)),
                timeout=60.0
            )
        except asyncio.TimeoutError:
            trade_logger.error(f"TradeDecisionExpert 调用超时 | {symbol} | {event_id}")
            td_output = {
                "decision": "NO_ACTION",
                "should_execute": False,
                "error": "LLM调用超时",
                "reasoning": ["TradeDecisionExpert调用超时（60秒）"]
            }
        except Exception as e:
            trade_logger.error(f"TradeDecisionExpert 调用失败 | {symbol} | {event_id} | {e}")
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
                if isinstance(td_output, dict) and "raw" in td_output and isinstance(td_output["raw"], str):
                    from agent_server.agents.experts.utils import _extract_json_from_text
                    extracted = _extract_json_from_text(td_output["raw"])
                    if extracted:
                        td_output = extracted
            except json.JSONDecodeError:
                # 如果直接解析失败，尝试提取 JSON
                from agent_server.agents.experts.utils import _extract_json_from_text
                extracted = _extract_json_from_text(td_output_str)
                if extracted:
                    td_output = extracted
                else:
                    td_output = {"raw": td_output_str, "decision": "NO_ACTION", "should_execute": False}
            except Exception as e:
                trade_logger.warning(f"解析 TradeDecisionExpert 输出失败 | {symbol} | {e}")
                td_output = {"raw": td_output_str, "decision": "NO_ACTION", "should_execute": False}

        decision = td_output.get("decision", "NO_ACTION")
        should_execute = td_output.get("should_execute", False)
        confidence = td_output.get("confidence", 0.0)
        
        trade_logger.info(f"交易决策结果 | {symbol} | decision={decision} | should_execute={should_execute} | confidence={confidence}")
        
        if "reasoning" in td_output:
            trade_logger.info(f"决策理由 | {symbol} | {json.dumps(td_output.get('reasoning'), ensure_ascii=False)}")

        # 7. 如果 should_execute==true，推送到交易队列
        if should_execute and decision in ["OPEN_LONG", "OPEN_SHORT", "CLOSE", "REDUCE"]:
            # 根据5m和15m K线数据计算合理的止盈止损
            calculated_tp_sl = self._calculate_tp_sl_from_klines(
                klines_5m, 
                klines_15m, 
                mark_price, 
                "LONG" if decision in ["OPEN_LONG"] else "SHORT"
            )
            trade_logger.info(f"计算止盈止损 | {symbol} | 5m波动={len(klines_5m)}根 | 15m波动={len(klines_15m)}根 | TP={calculated_tp_sl['tp_percent']}% | SL={calculated_tp_sl['sl_percent']}%")
            
            trade_json = self._build_trade_json(td_output, event_data, mark_price, calculated_tp_sl)
            if trade_json:
                success = await self._push_to_trade_queue(trade_json)
                td_output["trade_pushed"] = success
                td_output["trade_json"] = trade_json
                
                if success:
                    trade_logger.info(f"交易订单已推送 | {symbol} | {decision} | quantity={trade_json.get('sums')} | price={trade_json.get('openAvgPx')}")
                else:
                    trade_logger.error(f"交易订单推送失败 | {symbol} | {decision}")
            else:
                td_output["trade_pushed"] = False
                td_output["error"] = "无法构建交易 JSON"
                trade_logger.error(f"无法构建交易JSON | {symbol} | {decision}")
        else:
            td_output["trade_pushed"] = False
            td_output["reason"] = f"should_execute={should_execute}, decision={decision}"
            trade_logger.info(f"不执行交易 | {symbol} | reason={td_output.get('reason')}")

        # 记录完整决策过程到 Redis
        await self._save_decision_to_redis(symbol, event_id, td_output, query)

        trade_logger.info(f"=== 交易决策完成 === | {symbol} | {event_id} | decision={decision}")
        
        return self._safe_json_dumps({
            "trade_decision": td_output,
            "step2_result": prev_result
        })

    async def _save_decision_to_redis(self, symbol: str, event_id: str, decision: dict, query: dict):
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
            await rc.client.lpush(key, json.dumps(log_data, ensure_ascii=False))
            await rc.client.ltrim(key, 0, 999)  # 只保留最近 1000 条
            await rc.client.expire(key, 86400 * 7)  # 7 天过期
        except Exception as e:
            trade_logger.error(f"保存决策到Redis失败 | {symbol} | {e}")

