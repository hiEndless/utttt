from agno.workflow import StepInput
from agent_server.agents.experts.analysis.trade_event import TradeEventExpert
from agent_server.agent_context.builder import build_agent_context
from agent_server.agents.experts.analysis.utils.trade_core_data import abstract_trade_event
from agent_server.agent_workflow.components.base import BaseWorkflowComponent
from agent_server.utils.trade_event_recorder import get_recorder
import json
import asyncio
import time


class TradeEventExecutionComponent(BaseWorkflowComponent):
    def __init__(self):
        self.expert = TradeEventExpert()

    async def execute(self, ctx: StepInput) -> str:
        event_data = ctx.input
        print(f"--- 交易事件分析：{event_data.get('symbol')} ---")

        # 预判逻辑：如果是开仓事件或短线交易，跳过 LLM 分析以节省成本
        # event_type 格式通常为 "trade.open" 或 "trade.close"
        event_type_raw = event_data.get("event_type", "")
        event_action = event_type_raw.split(".")[-1].lower() if event_type_raw else "unknown"
        is_short_term = event_data.get("is_short_term", False)

        if event_action == "open" or is_short_term:
            print(f"  -> 跳过分析: Action={event_action}, ShortTerm={is_short_term}")
            return self._safe_json_dumps({
                "event_data": event_data,
                "output": {"skipped": True, "reason": f"action_{event_action}_shortterm_{is_short_term}"},
                "full_context": None,
            })

        symbol = event_data.get("symbol", "unknown")
        exchange = event_data.get("exchange", "binance")
        event_id = event_data.get("event_id")
        
        # 提取 trade_details 并抽象化
        trade_details = event_data.get("trade_details", {})
        trade_core = abstract_trade_event(trade_details)

        full_context = await self._fetch_market_context(exchange, symbol)
        agent_ctx = build_agent_context("trade_event", full_context)
        
        query = {
            "symbol": symbol,
            "exchange": exchange,
            "event_id": event_id,
            "trade_core": trade_core,
            "context": agent_ctx,
        }

        output_str = await self.expert.run(json.dumps(query, ensure_ascii=False))

        try:
            output_json = json.loads(output_str)
        except:
            output_json = {"raw": output_str}
        
        # 异步更新事件的市场背景快照
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
            "output": output_json,
            "full_context": full_context,
        })
