import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from agno.workflow import StepInput
from agent_server.agent_workflow.components.base import BaseWorkflowComponent
from agent_server.risk.execution_state_aggregator import aggregate_execution_state_and_store, key as get_execution_key
from agent_server.risk.global_overlay import aggregate_and_store_global_overlay
from agent_server.utils.redis_client import RedisClient


class RiskStateAggregationComponent(BaseWorkflowComponent):
    """
    负责将 PositionRiskExpert 的结果聚合生成 Execution State，并更新 Global Overlay。
    """

    async def execute(self, ctx: StepInput) -> str:
        prev_result = self._parse_step_content(ctx.previous_step_content)

        # Unpack previous result (from PositionRiskExecutionComponent)
        event_data = prev_result.get("event_data", {})
        if not event_data:
            # Fallback if structure is nested in step2_result (from PositionRiskExecutionComponent return format)
            step2_result = prev_result.get("step2_result", {})
            event_data = step2_result.get("event_data", {})
            # If still empty, try to get from prev_result directly (maybe passed through)
            if not event_data:
                event_data = prev_result.get("step1_result", {}).get("event_data", {})

        symbol = event_data.get("symbol")
        exchange = event_data.get("exchange", "binance")

        print(f"--- 状态聚合执行：{symbol} ---")

        # PositionRiskExecutionComponent returns:
        # {
        #   "decisions": [...],
        #   "risk_results": [...],
        #   "queries": [...],
        #   "step2_result": ...
        # }
        decisions = prev_result.get("decisions", [])
        risk_results = prev_result.get("risk_results", [])

        # 如果没有决策结果（可能被跳过或无持仓），直接尝试更新 global overlay (以防有其他并发更新)
        # 但如果是“无持仓”导致的跳过，是否需要生成 execution state? 不需要。
        if not decisions:
            print("  -> 无决策结果，仅刷新全局风控状态")
            global_overlay = await aggregate_and_store_global_overlay(exchange)
            return self._safe_json_dumps({
                "execution_states": [],
                "global_overlay": global_overlay,
                "prev_result": prev_result
            })

        # Get Signal Validation Output (needed for risk regime label)
        # It is inside step2_result -> output
        step2_result = prev_result.get("step2_result", {})
        sv_output = step2_result.get("output")
        decision_output = step2_result.get("decision_output")

        # 1. Generate & Store Execution State for each position
        generated_states = []

        # Need Redis client to fetch previous execution state
        rc = RedisClient()
        queries = prev_result.get("queries", [])

        for i, decision_item in enumerate(decisions):
            # decision_item: { "trade_id": ..., "side": ..., "decision": ..., "details": ... }
            trade_id = decision_item.get("trade_id")
            # risk_action_output is inside 'details'
            # If details has 'payload', use it, else use details itself
            details = decision_item.get("details", {})
            risk_action_output = details.get("payload", details)

            # Fetch previous execution state
            # execution_state_aggregator doesn't provide a fetch function, we construct key and get
            exec_key = get_execution_key(exchange, trade_id, symbol)
            prev_state_str = await rc.get(exec_key)
            prev_state = None
            if prev_state_str:
                try:
                    prev_state = json.loads(prev_state_str)
                except:
                    pass

            # Extract execution_constraint from the corresponding query
            # We assume decisions order matches queries order (guaranteed by PositionRiskExecutionComponent)
            execution_constraint = None
            if i < len(queries):
                execution_constraint = queries[i].get("execution_constraint")

            # Aggregate and Store
            # Note: signal_validation_output is optional but recommended
            exec_state = await aggregate_execution_state_and_store(
                risk_action_output=risk_action_output,
                signal_validation_output=sv_output,
                previous_execution_state=prev_state,
                execution_constraint=execution_constraint,
                decision_output=decision_output,
                exchange=exchange,
                trade_id=trade_id,
                symbol=symbol
            )
            generated_states.append({
                "trade_id": trade_id,
                "symbol": symbol,
                "state": exec_state
            })
            print(f"  -> 更新持仓状态: {symbol} / {trade_id}")

        # 2. Update Global Overlay
        print(f"  -> 刷新全局风控状态: {exchange}")
        global_overlay = await aggregate_and_store_global_overlay(exchange)

        return self._safe_json_dumps({
            "execution_states": generated_states,
            "global_overlay": global_overlay,
            "prev_result": prev_result
        })
