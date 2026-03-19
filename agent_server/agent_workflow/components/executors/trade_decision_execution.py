"""
交易决策执行组件：基于 pre_decision_structure、signal_validation、execution_constraint 做出开仓决策
数据源、分析逻辑、输出格式均确定，无模糊流程
"""

import asyncio
import json
import time
import logging
from typing import Dict, Optional, List, Any
from agno.workflow import StepInput
from agent_server.agents.experts.analysis.trade_decision import TradeDecisionExpert
from agent_server.agent_workflow.components.base import BaseWorkflowComponent
from agent_server.tools.price_fetcher import get_mark_price_from_redis
from agent_server.utils.trade_precision import format_price, format_quantity
from agent_server.risk.global_overlay import (
    _read_global_overlay_raw,
    check_global_permission,
    get_global_risk_narrative,
)
from agent_server.risk.execution_boundary import ExecutionBoundary
from agent_server.agent_context.builder import build_agent_context
from agent_server.agent_context.market_structure.technical_context import build_technical_context

trade_logger = logging.getLogger("trade_decision")
ai_reasoning_logger = logging.getLogger("trade_ai_reasoning")


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
        host = getattr(settings, "trade_redis_host",
                       None) or settings.redis_host
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
        from agent_server.utils.trade_push import push_trade_to_redis
        return await push_trade_to_redis(
            trade_json,
            queue_name=self.trade_queue_name,
            redis_config=self._get_trade_redis_config(),
        )

    def _build_trade_json(self, decision: Dict, event_data: Dict,
                          mark_price: float) -> Optional[Dict]:
        """
        根据决策构建交易 JSON。

        约定（与 trade 服务 & 测试脚本保持一致）：
        - order_type 仅使用业务含义: "open" / "close" / "reduce"
        - tp_trigger_px / sl_trigger_px **始终为具体价格，不再转换为百分比**
        - price / quantity 会按本地规则做精度截断，避免触发 Binance -1111
        """
        try:
            order_type = decision.get("order_type")
            if not order_type or order_type not in ("open", "close", "reduce"):
                return None

            symbol = decision.get("symbol")
            position_side = decision.get("position_side", "LONG")
            side = decision.get("side", "BUY")
            leverage = float(decision.get("leverage", 20.0))
            quantity = decision.get("quantity", "0")
            # LLM 按 prompt 约定返回的就是价格，这里仅做 float 转换 & 精度格式化
            tp_px_raw = float(decision.get("tp_trigger_px", 0) or 0)
            sl_px_raw = float(decision.get("sl_trigger_px", 0) or 0)

            if not quantity or quantity in ("0", 0):
                margin = float(decision.get("margin", 200.0))
                quantity = margin * leverage / mark_price if mark_price > 0 else 0.01

            # 与交易服务统一的数量/价格精度处理
            fmt_order_type = "open" if order_type == "open" else "close"
            qty_str = format_quantity(
                quantity,
                symbol,
                order_type=fmt_order_type,
                price=mark_price,
            )
            open_px = float(format_price(mark_price,
                                         symbol)) if mark_price > 0 else 0.0

            # 止盈止损：直接使用价格模式（与 trade 服务脚本保持一致）
            tp_price_fmt = float(format_price(
                tp_px_raw, symbol)) if tp_px_raw > 0 else 0.0
            sl_price_fmt = float(format_price(
                sl_px_raw, symbol)) if sl_px_raw > 0 else 0.0

            # trade_trigger_mode：若上游未显式给出，则有价格时默认开启，否则关闭
            trade_trigger_mode = int(
                decision.get(
                    "trade_trigger_mode",
                    1 if (tp_price_fmt > 0 or sl_price_fmt > 0) else 0,
                ))

            return {
                "order_type": order_type,
                "symbol": symbol,
                "positionSide": position_side,
                "side": side,
                "leverage": leverage,
                "sums": qty_str,
                "quantity": qty_str,  # 兼容 crawler 可能使用的字段名
                "openAvgPx": open_px,
                "task_id": 23,
                "user_id": 2,
                "api_id": 0,
                "trade_trigger_mode": trade_trigger_mode,
                # 与 trade 服务保持一致：这里直接传「价格」而非百分比
                "tp_trigger_px": tp_price_fmt,
                "sl_trigger_px": sl_price_fmt,
                "acc": {
                    "key": "",
                    "secret": "",
                    "passphrase": "",
                    "proxies": {},
                    "exchange": 2
                },
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
        technical_context: Optional[Dict] = None,
    ) -> Dict:
        """构建符合 prompt 的确定格式 query（对齐风控 Agent 输入结构）"""
        symbol = event_data.get("symbol", "")
        exchange = event_data.get("exchange", "binance")
        event_id = event_data.get("event_id", "")
        direction = event_data.get("direction", "neutral")
        ac = event_data.get("analysis_context") or {}
        l1_score = float(
            event_data.get("confidence_numeric")
            or event_data.get("l1_total_score") or ac.get("l1_total_score", 0))
        tf_hint = event_data.get("tf_hint") or ac.get("tf_hint") or []

        # 提取realtime_market_data（如果存在）
        realtime_data = market_structure.get("realtime_market_data", {})

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
                "risk_exposure_flags": sv_output.get("risk_exposure_flags",
                                                     []),
                "audit_confidence": sv_output.get("audit_confidence", {}),
            },
            "execution_constraint": execution_constraint,
            "global_risk_overlay": global_risk_desc,
            "mark_price": mark_price,
            "realtime_market_data": realtime_data,  # 实时市场数据（大订单、爆仓）
            "technical_context": technical_context or {},  # Redis klines 提取的周期性/空间特征
        }

    async def execute(self, ctx: StepInput) -> str:
        prev_result = self._parse_step_content(ctx.previous_step_content)
        event_data = prev_result.get("event_data") or prev_result.get(
            "step2_result", {}).get("event_data") or {}
        if not event_data:
            trade_logger.warning("无 event_data，跳过交易决策")
            return self._safe_json_dumps({
                "trade_decision": {
                    "decision": "NO_ACTION",
                    "reason": "missing_event_data"
                }
            })

        symbol = event_data.get("symbol")
        exchange = event_data.get("exchange", "binance")
        event_id = event_data.get("event_id", "")
        route = str(event_data.get("route", "")).lower()

        if not symbol:
            trade_logger.warning("无法获取 symbol，跳过交易决策")
            return self._safe_json_dumps({
                "trade_decision": {
                    "decision": "NO_ACTION",
                    "reason": "missing_symbol"
                }
            })

        if route == "trade" or "trade." in str(event_data.get(
                "event_type", "")):
            trade_logger.debug(f"交易事件类型，不执行开仓决策: {symbol}")
            return self._safe_json_dumps({
                "trade_decision": {
                    "decision": "NO_ACTION",
                    "reason": "trade_event"
                }
            })

        direction = (event_data.get("direction") or "neutral").strip().lower()
        l1_score = float(
            event_data.get("l1_total_score")
            or (event_data.get("analysis_context") or {}).get(
                "l1_total_score", 0))
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

        # 从 Redis klines 提取“近期高低点/ATR/区间位置”等周期性与空间特征（用于过滤追高/追低 + 生成TP/SL）
        technical_context = {}
        try:
            if mark_price and mark_price > 0:
                technical_context = await build_technical_context(exchange, symbol, ref_price=mark_price)
        except Exception as e:
            trade_logger.debug(f"构建 technical_context 失败: {e}")

        global_overlay_data = await _read_global_overlay_raw(exchange)
        global_risk_desc = get_global_risk_narrative(global_overlay_data) or ""

        query = self._build_query(
            event_data=event_data,
            sv_output=sv_output,
            execution_constraint=execution_constraint,
            market_structure=market_structure,
            mark_price=mark_price,
            global_risk_desc=global_risk_desc,
            technical_context=technical_context,
        )

        ai_reasoning_logger.info(
            f"[推理开始] event_id={event_id} symbol={symbol} direction={direction} l1_score={l1_score:.2f}"
        )
        ai_reasoning_logger.info(
            f"[推理输入] query={json.dumps(query, ensure_ascii=False)}")

        try:
            td_output_str = await asyncio.wait_for(
                self.expert.run(query),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            td_output = {
                "decision": "NO_ACTION",
                "should_execute": False,
                "error": "LLM 超时"
            }
            trade_logger.warning(
                f"TradeDecisionExpert 超时 | {symbol} | {event_id}")
            ai_reasoning_logger.warning(
                f"[推理异常] event_id={event_id} symbol={symbol} error=LLM超时")
        except Exception as e:
            trade_logger.error(
                f"TradeDecisionExpert 调用失败 | {symbol} | {event_id} | error={e}",
                exc_info=True)
            td_output = {
                "decision": "NO_ACTION",
                "should_execute": False,
                "error": str(e)
            }
            ai_reasoning_logger.error(
                f"[推理异常] event_id={event_id} symbol={symbol} error={e}")
        else:
            ai_reasoning_logger.info(
                f"[推理原始输出] event_id={event_id} raw={td_output_str}")
            try:
                parsed = json.loads(td_output_str) if isinstance(
                    td_output_str, str) else td_output_str
                if not isinstance(parsed, dict):
                    parsed = {
                        "decision": "NO_ACTION",
                        "should_execute": False,
                        "error": "LLM 返回非 dict"
                    }
                td_output = parsed
                if isinstance(td_output, dict) and "raw" in td_output:
                    from agent_server.agents.utils import _extract_json_from_text
                    ext = _extract_json_from_text(td_output.get("raw", ""))
                    if ext:
                        td_output = ext
            except json.JSONDecodeError:
                from agent_server.agents.utils import _extract_json_from_text
                ext = _extract_json_from_text(td_output_str)
                td_output = ext if ext else {
                    "raw": td_output_str,
                    "decision": "NO_ACTION",
                    "should_execute": False
                }

        if not isinstance(td_output, dict):
            td_output = {
                "decision": "NO_ACTION",
                "should_execute": False,
                "error": "解析结果非 dict"
            }
        decision = td_output.get("decision", "NO_ACTION")
        should_execute = td_output.get("should_execute", False)

        if not check_global_permission(global_overlay_data, "open"):
            should_execute = False
            td_output["should_execute"] = False
            td_output["reason"] = "全局风控禁止开仓"

        trade_pushed = False
        if should_execute and decision in ("OPEN_LONG", "OPEN_SHORT"):
            trade_json = self._build_trade_json(td_output, event_data,
                                                mark_price)
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

        ai_reasoning_logger.info(
            f"[推理完成] event_id={event_id} symbol={symbol} decision={decision} "
            f"should_execute={should_execute} trade_pushed={trade_pushed}")
        ai_reasoning_logger.info(
            f"[推理结果] parsed_output={json.dumps(td_output, ensure_ascii=False)}"
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
