from agno.workflow import StepInput
from agent_server.agent_workflow.components.base import BaseWorkflowComponent


class ResultAggregationComponent(BaseWorkflowComponent):
    async def execute(self, ctx: StepInput) -> str:
        prev_result = self._parse_step_content(ctx.previous_step_content)
        risk_results = prev_result["risk_results"]
        queries = prev_result["queries"]
        step1 = prev_result["step1_result"]

        print(f"--- [Step 4] Result Aggregation ---")

        decisions = []
        for q, r in zip(queries, risk_results):
            pos_snapshot = q.get("position_snapshot", {})
            pos_side = pos_snapshot.get("position_side", "NONE")
            trade_id = pos_snapshot.get("trade_id")  # 提取交易ID

            payload = r.get("payload", r)
            decision = payload.get("recommended_action", "HOLD")

            decisions.append({
                "trade_id": trade_id,  # 添加显式交易ID
                "side": pos_side,
                "decision": decision,
                "details": r
            })

        return self._safe_json_dumps({
            "decisions": decisions,
            "queries": queries,
            "risk_results": risk_results,
            "step1_result": step1
        })
