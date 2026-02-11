import asyncio
import json
import time
from typing import Dict, Optional, List, Any
from agno.workflow import StepInput
from agent_server.tools.get_position import get_position
from agent_server.agent_context.builder import build_agent_context
from agent_server.agents.experts.analysis.position_risk import PositionRiskExpert
from agent_server.agent_workflow.components.base import BaseWorkflowComponent
from agent_server.utils.account import account_state
from agent_server.agents.experts.analysis.utils.execution_constraint_aggregator import ExecutionConstraintAggregator
from agent_server.risk.global_overlay import _read_global_overlay_raw, check_global_permission, get_global_risk_narrative


class PositionRiskExecutionComponent(BaseWorkflowComponent):
    """
    负责构建持仓风控的上下文（Prompt）并并发执行风控 Agent。
    合并了原有的 ContextEnrichment 和 RiskAssessment 步骤。
    支持决策层（DecisionExpert）的输入作为约束。
    """

    def __init__(self):
        self.expert = PositionRiskExpert()

    async def execute(self, ctx: StepInput) -> str:
        prev_result = self._parse_step_content(ctx.previous_step_content)

        event_data = prev_result.get("event_data", {})
        # 支持从 SignalValidation 直接过来，或者从 DecisionComponent 过来
        # 如果从 DecisionComponent 过来，sv_output 在 sv_output 字段
        # 如果从 SignalValidation 过来，output 就是 sv_output
        sv_output = prev_result.get("sv_output") or prev_result.get("output", {})
        decision_output = prev_result.get("decision_output", {})  # Optional from DecisionComponent

        full_context = prev_result.get("full_context")

        # 判断是否有skipped字段
        if prev_result.get("skipped"):
            print(f"--- 持仓风控跳过：{event_data.get('symbol')} (Previous Skipped) ---")
            return self._safe_json_dumps(prev_result)

        symbol = event_data.get("symbol")
        exchange = event_data.get("exchange")

        print(f"--- 持仓风控执行：{symbol} ---")

        # 1. 获取持仓 (优先用上游传递的)
        positions = prev_result.get("positions")
        if not positions:
            positions = get_position(exchange, symbol)

        # 针对交易事件，只评估对应方向的持仓
        if event_data.get("route") == "trade":
            trade_details = event_data.get("trade_details", {})
            target_side = trade_details.get("position_side")
            if target_side:
                positions = [
                    p for p in positions
                    if str(p.get("position_side")).upper() == str(target_side).upper()
                ]
                print(f"  -> [Trade Event] 仅评估 {target_side} 方向持仓")

        # 2. 准备上下文数据
        # 优先使用上游传递的 context，如果缺失则自行获取
        if full_context:
            context_to_use = full_context
        else:
            print(f"  -> 未找到上游 Context，正在自行获取...")
            context_to_use = await self._fetch_market_context(exchange, symbol)

        pr_ctx = build_agent_context("position_risk", context_to_use)

        ts_now = int(time.time() * 1000)

        # 3. 内部辅助函数：构建单个 Query
        async def build_query(position_snapshot: Dict):
            trade_id = position_snapshot.get("trade_id")
            pos_side = position_snapshot.get("position_side", "LONG")

            # 查找对应的决策输出 (Decision Output)
            # decision_output 可能是单个 dict，也可能是包含 results 列表的 dict (多空双开)
            my_decision = {}
            if decision_output:
                results = decision_output.get("results")
                if isinstance(results, list):
                    # 多空分开的结果，需匹配
                    for r in results:
                        # 假设 result 的 meta 里有 position_side
                        meta = r.get("meta", {})
                        if str(meta.get("position_side")).upper() == str(pos_side).upper():
                            my_decision = r
                            break
                    # 如果没找到 meta.position_side，尝试匹配 data 里的
                    if not my_decision:
                        # Fallback: try to find match in data part if structure is different
                        pass
                else:
                    # 单个结果，假设适用于当前持仓 (或单向持仓)
                    my_decision = decision_output

            # 聚合 Execution Constraints
            # 使用 ExecutionConstraintAggregator 将 SV 输出和 Decision 输出合并
            aggregator = ExecutionConstraintAggregator()

            # 提取 data 部分（如果是 {data: ..., meta: ...} 结构）
            d_out_data = my_decision.get("data", my_decision) if isinstance(my_decision, dict) else {}
            sv_output_data = sv_output.get("data", sv_output) if isinstance(sv_output, dict) else {}

            agg_result = aggregator.aggregate(sv_output_data, d_out_data)
            execution_constraint = agg_result.get("execution_constraint", {})

            # 获取账户风险状态
            account_risk_state = await account_state(exchange)
            initialMargin = float(position_snapshot.get("initialMargin", 0))
            account_risk_state["position_occupancy_ratio"] = initialMargin / account_risk_state.get("balance", 1)
            
            # [NEW] 获取 Global Risk Overlay (Cognitive Layer)
            # 同样使用 Internal Raw API + Narrative Adapter
            global_overlay_data = await _read_global_overlay_raw(exchange)
            global_risk_desc = get_global_risk_narrative(global_overlay_data)

            # 构造与 Demo 一致的简单 Query 结构，移除 operational_context 等额外逻辑
            return {
                "meta": {
                    "symbol": symbol,
                    "exchange": exchange,
                    "event_id": event_data.get("event_id"),
                    "trade_id": trade_id,
                    "ts": ts_now
                },
                "market_structure": pr_ctx,  # 注意：这里用 build_agent_context 的结果
                "position": position_snapshot,
                "account_risk_state": account_risk_state,
                "global_risk_overlay": global_risk_desc,
                "execution_constraint": execution_constraint,
            }

        # 4. 构建并执行任务
        queries = []
        tasks = []

        if not positions:
            print(f"  -> 无持仓，跳过风控评估")
        else:
            for pos in positions:
                # 构建 Prompt
                q = await build_query(pos)
                queries.append(q)

                # 立即提交任务
                trade_id = pos.get("trade_id", "UNKNOWN")
                side = pos.get("position_side", "UNKNOWN")
                print(f"  -> 提交风控任务: TradeID={trade_id}, 方向={side}")
                tasks.append(self.expert.run(json.dumps(q, ensure_ascii=False)))

        # 5. 等待并发结果
        results = []
        if tasks:
            results = await asyncio.gather(*tasks)

        parsed_results = []
        for r in results:
            try:
                parsed_results.append(json.loads(r))
            except:
                parsed_results.append({"raw": r})

        # --- Aggregation Logic ---
        decisions = []
        
        # [NEW] 读取 Global Overlay 进行硬性门控 (检查层)
        # 使用内部原始 API + 权限检查器
        global_overlay = await _read_global_overlay_raw(exchange)
        
        # ----------- 逐行处理每个持仓的风控结果 -----------
        for q, r in zip(queries, parsed_results):
            pos_snapshot = q.get("position", {})
            pos_side = pos_snapshot.get("position_side", "NONE")
            trade_id = pos_snapshot.get("trade_id")

            payload = r.get("payload", r)
            # PositionRiskExpert v1.0 输出结构: { "risk_action": ..., "exposure_delta": ..., "reasoning": ... }
            decision = payload.get("risk_action") or payload.get("suggestion") or "hold"
        # ----------- 结束 逐行处理 -----------
            
            # --- 硬性门控逻辑 (Fail-Safe) ---
            original_decision = decision
            gated = False
            
            # 使用 check_global_permission 内部处理 Fail-Safe 逻辑
            if not check_global_permission(global_overlay, decision):
                decision = "hold"
                gated = True
            
            if gated:
                reason = "全局门控：被风控协议拦截 (故障安全机制激活)"
                print(f"  -> [GATE] 拦截: {trade_id} {original_decision} -> {decision}")
                # 注入跟踪信息到 details
                if isinstance(r, dict):
                    r["system_override"] = reason
                    r["original_decision"] = original_decision
            # --------- 硬性门控逻辑 (Fail-Safe) ----------------

            decisions.append({
                "trade_id": trade_id,
                "side": pos_side,
                "decision": decision,
                "details": r
            })

        return self._safe_json_dumps({
            "decisions": decisions,
            "risk_results": parsed_results,
            "queries": queries,
            "step2_result": prev_result
        })
