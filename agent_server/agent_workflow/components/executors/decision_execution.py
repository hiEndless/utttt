import json
import time
from typing import Dict, Any, List
from agno.workflow import StepInput
from agent_server.agent_workflow.components.base import BaseWorkflowComponent
from agent_server.agents.experts.orchestration.decision import DecisionExpert
from agent_server.agents.experts.orchestration.utils import transform_positions_to_decision_context
from agent_server.tools.get_position import get_position
from agent_server.agent_context.builder import build_agent_context
from agent_server.agent_context.market_structure.holding_context_from_positions import build_holding_context_from_positions

class DecisionExecutionComponent(BaseWorkflowComponent):
    def __init__(self):
        self.expert = DecisionExpert()

    async def execute(self, ctx: StepInput) -> str:
        prev_result = self._parse_step_content(ctx.previous_step_content)
        
        # Unpack previous result (from SignalValidationComponent)
        event_data = prev_result.get("event_data", {})
        sv_output = prev_result.get("output", {})
        sv_output_meta = sv_output.pop("meta")

        full_context = prev_result.get("full_context", {})
        
        symbol = event_data.get("symbol")
        exchange = event_data.get("exchange")
        
        print(f"--- 决策层执行：{symbol} ---")

        # 1. Get Positions
        positions = sv_output.pop("positions")
        if not positions:
             print("  -> 无持仓，跳过决策层")
             return self._safe_json_dumps({
                "skipped": True,
                "reason": "no_positions",
                "event_data": event_data,
                "sv_output": sv_output,
                "full_context": full_context
             })

        # 2. Build Context
        holding_context = build_holding_context_from_positions(positions)
        holding_horizon = holding_context.get("horizon")
        
        # Reuse full_context if available, otherwise fetch
        if not full_context:
             full_context = await self._fetch_market_context(exchange, symbol)

        market_structure = build_agent_context("decision", full_context, horizon=holding_horizon)

        # 3. Transform Positions
        position_context = transform_positions_to_decision_context(
            positions,
            signal=sv_output, # signal_verdict from SV
            market_structure=market_structure,
        )

        # 4. Build Query
        query = {
            "meta": {
                "symbol": symbol,
                "exchange": exchange,
                "event_id": event_data.get("event_id"),
                "ts": int(time.time() * 1000)
            },
            "market_structure": market_structure,
            "signal_verdict": sv_output,
            "position_state": position_context,
            "positions": positions, 
        }

        # 5. Run Expert
        # Expert handles dual-position splitting internally
        decision_output_str = await self.expert.run(query)
        
        try:
            decision_output = json.loads(decision_output_str)
        except:
            decision_output = {"raw": decision_output_str}

        # 补回meta
        sv_output["meta"] = sv_output_meta

        return self._safe_json_dumps({
            "event_data": event_data,
            "sv_output": sv_output,
            "decision_output": decision_output,
            "full_context": full_context,
            "positions": positions
        })
