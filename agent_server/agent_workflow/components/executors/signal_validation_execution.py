from agno.workflow import StepInput
from agent_server.agents.experts.analysis.signal_validation import SignalValidationExpert
from agent_server.agent_context.builder import build_agent_context
from agent_server.agent_context.market_structure.holding_context_from_positions import build_holding_context_from_positions
from agent_server.agent_context.market_structure import output as market_structure_output
from agent_server.agents.experts.analysis.utils.signal_cropper import crop_signal
from agent_server.agent_workflow.components.base import BaseWorkflowComponent
from agent_server.utils.trade_event_recorder import get_recorder
from agent_server.tools.get_position import get_position
from agent_server.config import settings
import json
import asyncio


class SignalValidationComponent(BaseWorkflowComponent):
    def __init__(self):
        self.expert = SignalValidationExpert()

    async def execute(self, ctx: StepInput) -> str:
        event_data = ctx.input
        print(f"--- 信号验证：{event_data.get('symbol')} ---")

        # 1. Crop signal
        cropped_signal = crop_signal(event_data)

        # 2. Get basic info
        symbol = event_data.get("symbol", "unknown")
        exchange = event_data.get("exchange", "binance")
        event_id = event_data.get("event_id")
        direction = event_data.get("direction")
        event_type = event_data.get("route")  # event_type maps to route

        # 3. Get positions and holding context
        positions = get_position(exchange, symbol)
        holding_context = build_holding_context_from_positions(positions)
        holding_horizon = holding_context.get("horizon")

        # 4. Build agent context
        # 在流程入口处实时生成最新的市场结构上下文，并会自动写入 Redis 供后续步骤使用
        full_context = await market_structure_output.build_output(exchange, symbol)
        agent_ctx = build_agent_context("signal_validation", full_context, horizon=holding_horizon)

        # 5. Construct query
        query = {
            "meta": {
                "symbol": symbol,
                "exchange": exchange,
                "event_id": event_id,
                "event_type": event_type,
                "direction": direction
            },
            "positions": positions,
            "final_event": cropped_signal,
            "context": agent_ctx,
        }

        # 6. Run expert
        # Load user specific config (TODO: DB)
        user_config = {}
        risk_cfg = {**settings.risk_defaults, **user_config}
        risk_mode = risk_cfg.get("risk_mode", "normal")

        sv_output_str = await self.expert.run(query, risk_mode=risk_mode)

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
