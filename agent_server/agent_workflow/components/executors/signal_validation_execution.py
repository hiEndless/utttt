from agno.workflow import StepInput
from agent_server.agents.experts.analysis.signal_validation import SignalValidationExpert
from agent_server.agent_context.builder import build_agent_context
from agent_server.agents.experts.analysis.utils.tf_validation import compute_tf_validation
from agent_server.agent_context.utils.crowd_interpreter import build_crowd_interpretation
from agent_server.agent_context.utils.crowd_trend_analysis import enrich_and_clean_crowd_context
from agent_server.agent_workflow.components.base import BaseWorkflowComponent
from agent_server.utils.trade_event_recorder import get_recorder
from agent_server.config import settings
import json
import asyncio
import time


class SignalValidationComponent(BaseWorkflowComponent):
    def __init__(self):
        self.expert = SignalValidationExpert()

    async def execute(self, ctx: StepInput) -> str:
        event_data = ctx.input
        print(f"--- 信号验证：{event_data.get('symbol')} ---")

        symbol = event_data.get("symbol", "unknown")
        exchange = event_data.get("exchange", "binance")
        direction = event_data.get("direction")
        tf_hint = event_data.get("tf_hint")
        event_id = event_data.get("event_id")  # 提取 event_id

        tf_validation = compute_tf_validation(symbol, exchange, direction, tf_hint)

        full_context = await self._fetch_market_context(exchange, symbol)
        agent_ctx = build_agent_context("signal_validation", full_context)

        agent_ctx["crowd_state"], agent_ctx["crowd_trend_analysis"] = await enrich_and_clean_crowd_context(
            exchange, symbol, agent_ctx.get("crowd_state", {})
        )

        market_snapshot = dict(full_context or {})
        market_snapshot["crowd_trend_analysis"] = agent_ctx.get("crowd_trend_analysis") or {}

        interpretation = build_crowd_interpretation(market_snapshot, direction)
        agent_ctx["crowd_interpretation"] = interpretation

        ts_now = int(time.time() * 1000)

        query = {
            "symbol": symbol,
            "exchange": exchange,
            "event_id": event_id,  # 传递 event_id 给 Agent
            "ts_now": ts_now,
            "final_event": {
                "event_type": event_data.get("route"),
                "direction": direction,
                "final_priority": event_data.get("final_priority"),
                "confidence": event_data.get("confidence"),
                "confidence_numeric": event_data.get("confidence_numeric"),
                "tf_hint": tf_hint or [],
                "analysis_context": event_data.get("analysis_context") or event_data.get("l1_total_score"),
            },
            "tf_validation": tf_validation,
            "context": agent_ctx,
        }

        # Load user specific config (TODO: DB)
        user_config = {}
        risk_cfg = {**settings.risk_defaults, **user_config}
        risk_mode = risk_cfg.get("risk_mode", "normal")

        sv_output_str = await self.expert.run(json.dumps(query, ensure_ascii=False), risk_mode=risk_mode)

        try:
            sv_output = json.loads(sv_output_str)
        except:
            sv_output = {"raw": sv_output_str}
        
        # 异步更新事件的市场背景快照（不阻塞当前流程）
        if event_id and full_context:
            recorder = get_recorder()
            asyncio.create_task(
                recorder.update_event_context(
                    event_id=event_id,
                    exchange=exchange,
                    symbol=symbol,
                    market_context=full_context
                )
            )

        return self._safe_json_dumps({
            "event_data": event_data,
            "output": sv_output,
            "full_context": full_context,
        })
