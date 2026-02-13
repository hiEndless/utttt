import json
import time
from typing import Dict, Any, List
from agno.workflow import StepInput
from agent_server.agent_workflow.components.base import BaseWorkflowComponent
from agent_server.agents.experts.orchestration.decision import DecisionExpert
from agent_server.agents.experts.orchestration.utils import transform_positions_to_decision_context
from agent_server.tools.get_position import get_position
from agent_server.agent_context.builder import build_agent_context
from agent_server.agent_context.market_structure.holding_context_from_positions import \
    build_holding_context_from_positions


class DecisionExecutionComponent(BaseWorkflowComponent):
    def __init__(self):
        self.expert = DecisionExpert()

    async def execute(self, ctx: StepInput) -> str:
        prev_result = self._parse_step_content(ctx.previous_step_content)

        event_data = prev_result.get("event_data", {}) or {}
        full_context = prev_result.get("full_context", {}) or {}

        symbol = event_data.get("symbol")
        exchange = event_data.get("exchange")

        print(f"--- 决策层执行：{symbol} ---")

        output = prev_result.get("output", {})

        route = str(event_data.get("route") or "").lower()
        event_type = str(event_data.get("event_type") or "").lower()
        expert_key = "trade_behavior" if (route == "trade" or event_type.startswith("trade.")) else "signal_verdict"

        sv_output_meta = output.get("meta", {}) if isinstance(output.get("meta", {}), dict) else {}

        positions = output.get("positions") or prev_result.get("positions")
        if not positions:
            positions = get_position(exchange, symbol)
        if not positions:
            print("  -> 无持仓，跳过决策层")
            return self._safe_json_dumps({
                "skipped": True,
                "reason": "no_positions",
                "event_data": event_data,
                "output": output,
                "full_context": full_context,
                "positions": [],
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
            signal=output,  # signal_verdict from 工作流发起的agent
            market_structure=market_structure,
        )

        # 4. Build Query
        query = {
            "meta": {
                "symbol": symbol,
                "exchange": exchange,
                "event_id": event_data.get("event_id"),
                "trade_id": sv_output_meta.get("trade_id"),
                "ts": int(time.time() * 1000)
            },
            "market_structure": market_structure,
            expert_key: output,
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

        return self._safe_json_dumps({
            "event_data": event_data,
            "output": output,
            "decision_output": decision_output,
            "full_context": full_context,
            "positions": positions
        })
