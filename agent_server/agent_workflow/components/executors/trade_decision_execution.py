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
        try:
            rc = RedisClient()
            key = f"background:{exchange}:{symbol}:market_structure"
            data_str = await rc.get(key)
            if data_str:
                return json.loads(data_str) if isinstance(data_str, str) else data_str
            return None
        except Exception as e:
            trade_logger.debug(f"读取 market_structure 失败: {e}")
            return None

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

    def _build_trade_json(self, decision: Dict, event_data: Dict, mark_price: float) -> Optional[Dict]:
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
            tp_trigger_px = decision.get("tp_trigger_px", 0.0)
            sl_trigger_px = decision.get("sl_trigger_px", 0.0)
            trade_trigger_mode = decision.get("trade_trigger_mode", 1)
            order_type_binance = decision.get("order_type_binance", "MARKET")
            
            # 计算数量（如果未提供）
            if not quantity or quantity == "0":
                if order_type == "open":
                    # 开仓：根据保证金和杠杆计算
                    calculated_qty = margin * leverage / mark_price
                    quantity = str(int(calculated_qty))
                else:
                    # 平仓/减仓：需要从持仓获取，这里暂时返回 None
                    trade_logger.warning(f"平仓/减仓需要从持仓获取数量，暂不支持")
                    return None
            
            trade_json = {
                "order_type": order_type,
                "symbol": symbol,
                "positionSide": position_side,
                "side": side,
                "leverage": float(leverage),
                "sums": str(quantity),
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

        event_data = prev_result.get("event_data", {})
        sv_output = prev_result.get("sv_output", {})
        pr_result = prev_result.get("decisions", [])
        risk_results = prev_result.get("risk_results", [])

        symbol = event_data.get("symbol")
        exchange = event_data.get("exchange", "binance")
        event_id = event_data.get("event_id", "")
        
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
            summary = market_structure.get("summary", {})
            trade_logger.info(f"市场结构 | {symbol} | bias={summary.get('cross_period_bias')} | alignment={summary.get('alignment_score')}")
        else:
            trade_logger.warning(f"未找到market_structure | {symbol}")

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
        td_output_str = await self.expert.run(json.dumps(query, ensure_ascii=False))

        try:
            td_output = json.loads(td_output_str)
        except:
            td_output = {"raw": td_output_str}

        decision = td_output.get("decision", "NO_ACTION")
        should_execute = td_output.get("should_execute", False)
        confidence = td_output.get("confidence", 0.0)
        
        trade_logger.info(f"交易决策结果 | {symbol} | decision={decision} | should_execute={should_execute} | confidence={confidence}")
        
        if "reasoning" in td_output:
            trade_logger.info(f"决策理由 | {symbol} | {json.dumps(td_output.get('reasoning'), ensure_ascii=False)}")

        # 7. 如果 should_execute==true，推送到交易队列
        if should_execute and decision in ["OPEN_LONG", "OPEN_SHORT", "CLOSE", "REDUCE"]:
            trade_json = self._build_trade_json(td_output, event_data, mark_price)
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

