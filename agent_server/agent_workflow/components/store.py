import time
from agno.workflow import StepInput
from agent_server.utils.persistence import WorkflowPersistence
from agent_server.agent_workflow.components.base import BaseWorkflowComponent


class StoreComponent(BaseWorkflowComponent):

    async def execute(self, ctx: StepInput) -> str:
        prev_result = self._parse_step_content(ctx.previous_step_content)

        decisions = prev_result["decisions"]
        risk_results = prev_result["risk_results"]
        queries = prev_result["queries"]
        step1 = prev_result["step1_result"]

        print(f"--- [步骤 5] 持久化 ---")

        # 针对每个 Trade ID 分别保存 Trace
        # 这样可以确保每个 Trade ID 都有自己独立的、完整的决策历史
        saved_ids = []
        ts = int(time.time() * 1000)

        for i, decision in enumerate(decisions):
            trade_id = decision.get("trade_id")
            if not trade_id:
                continue
            
            # 找到对应的 Query 和 Result
            # 注意：这里假设 decisions, queries, risk_results 的顺序是一致的
            # 由于我们之前的 zip 逻辑，这是有保证的
            query = queries[i]
            result = risk_results[i]

            single_trade_trace = {
                "trade_id": trade_id,    # 核心业务主键
                "ts": ts,
                "event_input": step1["event_data"],
                "signal_validation": {
                    "output": step1["sv_output"]
                },
                "risk_assessment": {
                    "query_snapshot": query,
                    "result": result
                },
                "final_decision": decision
            }

            # 使用 trade_id 作为主要索引进行保存
            # 注意：这里我们传入 trade_id，底层的 save_trace 应该处理"追加"逻辑
            # 或者我们构造一个唯一的 Key，如 trade_id:ts
            await WorkflowPersistence.save_trace(trade_id, single_trade_trace)
            saved_ids.append(trade_id)
        
        return self._safe_json_dumps({"trace_id": trade_id, "saved_trades": saved_ids, "status": "completed"})
