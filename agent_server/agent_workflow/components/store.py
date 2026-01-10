import time
import asyncio
from agno.workflow import StepInput
from agent_server.agent_workflow.components.base import BaseWorkflowComponent
from agent_server.utils.trade_event_recorder import get_recorder


class StoreComponent(BaseWorkflowComponent):

    async def execute(self, ctx: StepInput) -> str:
        prev_result = self._parse_step_content(ctx.previous_step_content)

        decisions = prev_result["decisions"]
        risk_results = prev_result["risk_results"]
        queries = prev_result["queries"]
        step1 = prev_result["step1_result"]

        print(f"--- 持久化 ---")

        recorder = get_recorder()
        save_tasks = []
        
        # 获取事件基础信息
        event_data = step1.get("event_data", {})
        event_id = event_data.get("event_id")
        
        # 1. 保存 Signal Validation 结果 (通用分析)
        # 这会关联到该 event_id 下的所有 trade_events 记录
        sv_output = step1.get("sv_output")
        if event_id and sv_output:
            save_tasks.append(
                recorder.save_agent_analysis(
                    event_id=event_id, 
                    agent_name="signal_validation", 
                    analysis_data=sv_output
                )
            )

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

            # 2. 保存 Position Risk 结果 (特定持仓分析)
            if event_id and result:
                save_tasks.append(
                    recorder.save_agent_analysis(
                        event_id=event_id,
                        agent_name="position_risk",
                        analysis_data=result,
                        trade_id=trade_id
                    )
                )

            saved_ids.append(trade_id)
        
        # 并发执行所有保存任务
        if save_tasks:
            await asyncio.gather(*save_tasks)
            print(f"已保存 {len(save_tasks)} 条分析记录到数据库")
        
        return self._safe_json_dumps({"saved_trades": saved_ids, "status": "completed"})
