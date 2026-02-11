import time
from typing import Dict, Any
from agno.workflow import StepInput
from agent_server.agent_workflow.components.base import BaseWorkflowComponent
from agent_server.agents.experts.background.market_structure import MarketStructureExpert
from agent_server.agent_context.builder import build_agent_context
from agent_server.utils.trade_event_recorder import get_recorder


class MarketStructureExecutionComponent(BaseWorkflowComponent):
    """
    执行市场结构分析专家 (MarketStructureExpert)。
    通常作为工作流的最后一步，用于生成复盘用的系统认知描述。
    """

    async def execute(self, ctx: StepInput) -> str:
        # 1. 解析上下文，获取 symbol 和 exchange
        # 尝试从上一步的输出中回溯原始事件数据
        prev_output = self._parse_step_content(ctx.previous_step_content)
        
        event_data = self._find_event_data(prev_output)
        
        symbol = event_data.get("symbol")
        event_id = event_data.get("event_id")
        exchange = event_data.get("exchange", "binance")
        ts = event_data.get("timestamp") or int(time.time() * 1000)
        
        if not symbol:
            print("[MarketStructureExecution] Warning: Symbol not found in context, skipping.")
            return self._safe_json_dumps({
                "status": "skipped",
                "reason": "symbol_not_found",
                "prev_result": prev_output
            })
            
        print(f"--- 市场结构分析执行：{symbol} ---")

        # 2. 构建 Agent Context
        # 使用专门的 output.build_output 获取完整的 redis 状态
        try:
            full_context = await self._fetch_market_context(exchange, symbol)
            query = build_agent_context("market_structure", full_context)
            
            # 补全 query 中的 meta 信息 (MarketStructureExpert.run 需要这些字段)
            query["symbol"] = symbol
            query["ts"] = ts
            
            # 3. 运行 Expert
            expert = MarketStructureExpert()
            result_json = await expert.run(query)
            
            analysis_result = self._parse_step_content(result_json)
            
            # 4. 入库保存
            if event_id:
                try:
                    recorder = get_recorder()
                    await recorder.update_market_structure(event_id, analysis_result)
                except Exception as e:
                    print(f"[MarketStructureExecution] Save Error: {e}")
            
            return self._safe_json_dumps({
                "market_structure_analysis": analysis_result,
                "prev_result": prev_output
            })
            
        except Exception as e:
            print(f"[MarketStructureExecution] Error: {e}")
            # 即使分析失败，也不应导致整个工作流报错（因为它是非关键路径）
            return self._safe_json_dumps({
                "status": "failed",
                "error": str(e),
                "prev_result": prev_output
            })

    def _find_event_data(self, data: Any) -> Dict[str, Any]:
        """递归查找包含 symbol 的 event_data"""
        if not isinstance(data, dict):
            return {}
            
        # 1. 直接检查 event_data
        if "event_data" in data and isinstance(data["event_data"], dict) and data["event_data"]:
            return data["event_data"]
            
        # 2. 检查 prev_result (递归)
        if "prev_result" in data:
            found = self._find_event_data(data["prev_result"])
            if found: return found
            
        # 3. 检查 step2_result / step1_result 等常见嵌套
        for key in ["step2_result", "step1_result"]:
            if key in data:
                found = self._find_event_data(data[key])
                if found: return found
                
        return {}
