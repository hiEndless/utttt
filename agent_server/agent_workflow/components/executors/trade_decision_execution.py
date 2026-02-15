"""
交易决策执行组件：基于 pre_decision_structure、signal_validation、execution_constraint 做出开仓决策
数据源、分析逻辑、输出格式均确定，无模糊流程
"""

import asyncio
import json
import time
import hashlib
import logging
from typing import Dict, Optional, List, Any
from agno.workflow import StepInput
from agent_server.agents.experts.analysis.trade_decision import TradeDecisionExpert
from agent_server.agent_workflow.components.base import BaseWorkflowComponent
from agent_server.utils.redis_client import RedisClient
from agent_server.tools.price_fetcher import get_mark_price_from_redis
from agent_server.risk.global_overlay import (
    _read_global_overlay_raw,
    check_global_permission,
    get_global_risk_narrative,
)
from agent_server.risk.execution_boundary import ExecutionBoundary
from agent_server.agent_context.builder import build_agent_context

try:
    import redis
except ImportError:
    redis = None

trade_logger = logging.getLogger("trade_decision")


def _resolve_sv_output(prev_result: Dict) -> Dict:
    """从上游解析 signal_validation 输出（支持 output 或 step2_result.output）"""
    output = prev_result.get("output", {})
    step2 = prev_result.get("step2_result", {})
    if isinstance(step2, dict) and step2.get("output"):
        output = step2.get("output", output)
    if isinstance(output, dict) and output.get("agent_output"):
        return output.get("agent_output", output)
    return output if isinstance(output, dict) else {}


def _resolve_decision_output(prev_result: Dict) -> Dict:
    """从上游解析 decision_output（无持仓时为空）"""
    out = prev_result.get("decision_output") or {}
    step2 = prev_result.get("step2_result", {})
    if isinstance(step2, dict) and step2.get("decision_output"):
        out = step2.get("decision_output", out)
    return out if isinstance(out, dict) else {}


def _resolve_full_context(prev_result: Dict) -> Dict:
    """从上游解析 full_context（含 pre_decision_structure）"""
    ctx = prev_result.get("full_context") or {}
    step2 = prev_result.get("step2_result", {})
    if isinstance(step2, dict) and step2.get("full_context"):
        ctx = step2.get("full_context", ctx)
    return ctx if isinstance(ctx, dict) else {}


class TradeDecisionExecutionComponent(BaseWorkflowComponent):
    """
    交易决策执行组件：
    1. 从上游获取 pre_decision_structure、signal_validation、decision_output
    2. 使用 ExecutionBoundary 聚合 execution_constraint（无持仓时 decision_output 为空仍可生成）
    3. 构建确定格式的 query 调用 TradeDecisionExpert
    4. 若 should_execute==true，推送到 Redis 队列 TASK_ADD_TRADE
    """

    def __init__(self):
        self.expert = TradeDecisionExpert()
        self.trade_queue_name = "TASK_ADD_TRADE"
        self._trade_redis_config = None

    def _get_trade_redis_config(self) -> dict:
        if self._trade_redis_config:
            return self._trade_redis_config
        from agent_server.config import settings
        host = getattr(settings, "trade_redis_host", None) or settings.redis_host
        password = getattr(settings, "trade_redis_password", None)
        if password is None:
            password = settings.redis_password
        return {
            "host": host,
            "port": getattr(settings, "trade_redis_port", 6379),
            "password": password,
            "db": getattr(settings, "trade_redis_db", 8),
            "decode_responses": False,
        }

    async def _push_to_trade_queue(self, trade_json: Dict) -> bool:
        if not redis:
            trade_logger.error("redis 模块未安装，无法推送交易")
            return False
        try:
            symbol = trade_json.get("symbol", "")
            order_type = trade_json.get("order_type", "open")
            exchange = "binance"

            timestamp = int(time.time() * 1000)
            trade_str = json.dumps(trade_json, sort_keys=True, ensure_ascii=False)
            trade_hash = hashlib.md5(trade_str.encode()).hexdigest()[:8]
            order_id = f"{symbol}_{timestamp}_{order_type}_{trade_hash}"

            rc = RedisClient()
            order_key = f"trading:orders:{exchange}"
            if await rc.client.sismember(order_key, order_id):
                trade_logger.warning(f"订单已存在，跳过: {order_id} | {symbol}")
                return False

            if order_type == "open":
                position_key = f"trading:open_positions:{exchange}"
                if await rc.client.sismember(position_key, symbol):
                    trade_logger.warning(f"交易对已开仓，跳过: {symbol}")
                    return False

            cfg = self._get_trade_redis_config()
            password = cfg.get("password")
            if isinstance(password, str) and password.strip().lower() in ("none", "null", ""):
                password = None

            r = redis.Redis(
                host=cfg["host"],
                port=cfg["port"],
                password=password,
                db=cfg["db"],
                decode_responses=cfg.get("decode_responses", False),
                socket_connect_timeout=10,
                socket_timeout=10,
            )
            json_str = json.dumps(trade_json, ensure_ascii=False)
            result = r.lpush(self.trade_queue_name, json_str)
            r.close()

            if result:
                await rc.client.sadd(order_key, order_id)
                if order_type == "open":
                    await rc.client.sadd(f"trading:open_positions:{exchange}", symbol)
                elif order_type == "close":
                    await rc.client.srem(f"trading:open_positions:{exchange}", symbol)
                trade_logger.info(f"订单已推送: {order_id} | {symbol}")
                return True
            return False
        except Exception as e:
            trade_logger.error(f"推送交易失败: {e}")
            return False

    def _format_quantity(self, quantity, symbol: str, step_size: float = 0.001) -> str:
        try:
            from decimal import Decimal, ROUND_DOWN
            q = Decimal(str(float(quantity)))
            step = Decimal(str(step_size))
            rounded = (q // step) * step
            rounded = rounded.quantize(Decimal(str(step_size)), rounding=ROUND_DOWN)
            if rounded <= 0:
                rounded = step
            s = str(rounded)
            return s.rstrip("0").rstrip(".") if "." in s else s
        except Exception:
            return str(quantity)

    def _build_trade_json(
        self, decision: Dict, event_data: Dict, mark_price: float
    ) -> Optional[Dict]:
        """根据决策构建交易 JSON，tp/sl 支持价格或百分比"""
        try:
            order_type = decision.get("order_type")
            if not order_type or order_type not in ("open", "close", "reduce"):
                return None

            symbol = decision.get("symbol")
            position_side = decision.get("position_side", "LONG")
            side = decision.get("side", "BUY")
            leverage = float(decision.get("leverage", 20.0))
            quantity = decision.get("quantity", "0")
            tp_px = float(decision.get("tp_trigger_px", 0) or 0)
            sl_px = float(decision.get("sl_trigger_px", 0) or 0)

            if not quantity or quantity in ("0", 0):
                margin = float(decision.get("margin", 200.0))
                quantity = margin * leverage / mark_price if mark_price > 0 else 0.01

            qty_str = self._format_quantity(quantity, symbol)

            # 价格转百分比：下游队列使用百分比
            if tp_px > 0 and sl_px > 0 and mark_price > 0:
                if position_side == "LONG":
                    tp_pct = (tp_px - mark_price) / mark_price * 100
                    sl_pct = (mark_price - sl_px) / mark_price * 100
                else:
                    tp_pct = (mark_price - tp_px) / mark_price * 100
                    sl_pct = (sl_px - mark_price) / mark_price * 100
                if tp_pct <= 0 or sl_pct <= 0:
                    tp_pct, sl_pct = 3.0, 2.0
            else:
                tp_pct, sl_pct = 3.0, 2.0

            return {
                "order_type": order_type,
                "symbol": symbol,
                "positionSide": position_side,
                "side": side,
                "leverage": leverage,
                "sums": qty_str,
                "openAvgPx": float(mark_price),
                "task_id": 23,
                "user_id": 2,
                "api_id": 0,
                "trade_trigger_mode": 1,
                "tp_trigger_px": float(tp_pct),
                "sl_trigger_px": float(sl_pct),
                "acc": {"key": "", "secret": "", "passphrase": "", "proxies": {}, "exchange": 2},
                "flag": "1",
                "uniqueName": "ai_trading_system",
            }
        except Exception as e:
            trade_logger.error(f"构建交易 JSON 失败: {e}")
            return None

    def _build_query(
        self,
        event_data: Dict,
        sv_output: Dict,
        execution_constraint: Dict,
        market_structure: Dict,
        mark_price: float,
        global_risk_desc: str,
    ) -> Dict:
        """构建符合 prompt 的确定格式 query（对齐风控 Agent 输入结构）"""
        symbol = event_data.get("symbol", "")
        exchange = event_data.get("exchange", "binance")
        event_id = event_data.get("event_id", "")
        direction = event_data.get("direction", "neutral")
        ac = event_data.get("analysis_context") or {}
        l1_score = float(
            event_data.get("confidence_numeric")
            or event_data.get("l1_total_score")
            or ac.get("l1_total_score", 0)
        )
        tf_hint = event_data.get("tf_hint") or ac.get("tf_hint") or []

        return {
            "meta": {
                "symbol": symbol,
                "exchange": exchange,
                "event_id": event_id,
                "ts": int(time.time() * 1000),
            },
            "market_structure": market_structure,
            "trigger_event": {
                "direction": (direction or "neutral").strip().lower(),
                "l1_total_score": l1_score,
                "tf_hint": tf_hint,
                "analysis_context": ac,
            },
            "signal_validation": {
                "dominant_cycle": sv_output.get("dominant_cycle"),
                "cycle_weights": sv_output.get("cycle_weights", {}),
                "audit_breakdown": sv_output.get("audit_breakdown", {}),
                "risk_exposure_flags": sv_output.get("risk_exposure_flags", []),
                "audit_confidence": sv_output.get("audit_confidence", {}),
            },
            "execution_constraint": execution_constraint,
            "global_risk_overlay": global_risk_desc,
            "mark_price": mark_price,
        }

    async def execute(self, ctx: StepInput) -> str:
        prev_result = self._parse_step_content(ctx.previous_step_content)
        event_data = prev_result.get("event_data") or prev_result.get("step2_result", {}).get("event_data") or {}
        if not event_data:
            trade_logger.warning("无 event_data，跳过交易决策")
            return self._safe_json_dumps({"trade_decision": {"decision": "NO_ACTION", "reason": "missing_event_data"}})

        symbol = event_data.get("symbol")
        exchange = event_data.get("exchange", "binance")
        event_id = event_data.get("event_id", "")
        route = str(event_data.get("route", "")).lower()

        if not symbol:
            trade_logger.warning("无法获取 symbol，跳过交易决策")
            return self._safe_json_dumps({"trade_decision": {"decision": "NO_ACTION", "reason": "missing_symbol"}})

        if route == "trade" or "trade." in str(event_data.get("event_type", "")):
            trade_logger.debug(f"交易事件类型，不执行开仓决策: {symbol}")
            return self._safe_json_dumps({"trade_decision": {"decision": "NO_ACTION", "reason": "trade_event"}})

        direction = (event_data.get("direction") or "neutral").strip().lower()
        l1_score = float(
            event_data.get("l1_total_score")
            or (event_data.get("analysis_context") or {}).get("l1_total_score", 0)
        )
        trade_logger.info(
            f"=== 交易决策开始 === | {symbol} | {event_id} | direction={direction} | l1_score={l1_score:.2f}"
        )

        sv_output = _resolve_sv_output(prev_result)
        decision_output = _resolve_decision_output(prev_result)
        full_context = _resolve_full_context(prev_result)
        market_structure = build_agent_context("trade_decision", full_context)

        boundary = ExecutionBoundary()
        agg = boundary.aggregate(sv_output, decision_output or {})
        execution_constraint = agg.get("execution_constraint", {})

        mark_price = await get_mark_price_from_redis(exchange, symbol)
        if not mark_price or mark_price <= 0:
            trade_logger.warning(f"无法获取价格: {symbol}")
            mark_price = 0.0

        global_overlay_data = await _read_global_overlay_raw(exchange)
        global_risk_desc = get_global_risk_narrative(global_overlay_data) or ""

        query = self._build_query(
            event_data=event_data,
            sv_output=sv_output,
            execution_constraint=execution_constraint,
            market_structure=market_structure,
            mark_price=mark_price,
            global_risk_desc=global_risk_desc,
        )

        try:
            td_output_str = await asyncio.wait_for(
                self.expert.run(query),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            td_output = {"decision": "NO_ACTION", "should_execute": False, "error": "LLM 超时"}
            trade_logger.warning(f"TradeDecisionExpert 超时 | {symbol} | {event_id}")
        except Exception as e:
            trade_logger.error(f"TradeDecisionExpert 调用失败 | {symbol} | {event_id} | error={e}", exc_info=True)
            td_output = {"decision": "NO_ACTION", "should_execute": False, "error": str(e)}
        else:
            try:
                parsed = json.loads(td_output_str) if isinstance(td_output_str, str) else td_output_str
                if not isinstance(parsed, dict):
                    parsed = {"decision": "NO_ACTION", "should_execute": False, "error": "LLM 返回非 dict"}
                td_output = parsed
                if isinstance(td_output, dict) and "raw" in td_output:
                    from agent_server.agents.utils import _extract_json_from_text
                    ext = _extract_json_from_text(td_output.get("raw", ""))
                    if ext:
                        td_output = ext
            except json.JSONDecodeError:
                from agent_server.agents.utils import _extract_json_from_text
                ext = _extract_json_from_text(td_output_str)
                td_output = ext if ext else {"raw": td_output_str, "decision": "NO_ACTION", "should_execute": False}

        if not isinstance(td_output, dict):
            td_output = {"decision": "NO_ACTION", "should_execute": False, "error": "解析结果非 dict"}
        decision = td_output.get("decision", "NO_ACTION")
        should_execute = td_output.get("should_execute", False)

        if not check_global_permission(global_overlay_data, "open"):
            should_execute = False
            td_output["should_execute"] = False
            td_output["reason"] = "全局风控禁止开仓"

        trade_pushed = False
        if should_execute and decision in ("OPEN_LONG", "OPEN_SHORT"):
            trade_json = self._build_trade_json(td_output, event_data, mark_price)
            if trade_json:
                trade_pushed = await self._push_to_trade_queue(trade_json)
                td_output["trade_pushed"] = trade_pushed
                td_output["trade_json"] = trade_json
                if trade_pushed:
                    trade_logger.info(f"交易已推送: {symbol} | {decision}")
        else:
            td_output["trade_pushed"] = False

        reasoning = td_output.get("reasoning", [])
        r0 = str(reasoning[0]) if reasoning and reasoning[0] else ""
        reason_preview = (r0[:80] + "...") if len(r0) > 80 else r0
        fallback = td_output.get("error", "") or reason_preview
        trade_logger.info(
            f"=== 交易决策完成 === | {symbol} | {decision} | pushed={trade_pushed} | reason={fallback[:100]}"
        )

        out = {
            "trade_decision": td_output,
            "step2_result": prev_result.get("step2_result", prev_result),
            "prev_result": prev_result,
        }
        out["decisions"] = prev_result.get("decisions", [])
        out["risk_results"] = prev_result.get("risk_results", [])
        out["event_data"] = event_data
        out["queries"] = prev_result.get("queries", [])
        return self._safe_json_dumps(out)
