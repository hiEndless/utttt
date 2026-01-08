import asyncio
import json
import time
from typing import Dict, Optional, List
from agno.workflow import StepInput
from agent_server.tools.get_position import get_position
from agent_server.reducers.temporal_state_reducer import reduce_temporal_state
from agent_server.utils.redis_client import RedisClient
from agent_server.agent_context.builder import build_agent_context
from agent_server.agents.experts.analysis.position_risk import PositionRiskExpert
from agent_server.agent_workflow.components.base import BaseWorkflowComponent


class PositionRiskExecutionComponent(BaseWorkflowComponent):
    """
    负责构建持仓风控的上下文（Prompt）并并发执行风控 Agent。
    合并了原有的 ContextEnrichment 和 RiskAssessment 步骤。
    """

    def __init__(self):
        self.expert = PositionRiskExpert()

    async def execute(self, ctx: StepInput) -> str:
        prev_result = self._parse_step_content(ctx.previous_step_content)

        event_data = prev_result["event_data"]
        sv_output = prev_result["sv_output"]
        full_context = prev_result["full_context"]

        symbol = event_data.get("symbol")
        exchange = event_data.get("exchange")
        
        print(f"--- [步骤 2&3] 持仓风控执行：{symbol} ---")

        # 1. 获取持仓
        positions = get_position(exchange, symbol)
        
        # 2. 准备上下文数据
        agent_output = sv_output.get("agent_output", sv_output)
        verdict = agent_output.get("verdict", "UNKNOWN")
        
        # 优先使用上游传递的 context，如果缺失则自行获取
        if full_context:
            context_to_use = full_context
        else:
            print(f"  -> 未找到上游 Context，正在自行获取...")
            context_to_use = await self._fetch_market_context(exchange, symbol)

        pr_ctx = build_agent_context("position_risk", context_to_use)
        
        market_context = {
            "htf_trend": pr_ctx.get("market_state", {}).get("long_term", {}).get("direction", "unknown"),
            "ltf_structure": pr_ctx.get("market_state", {}).get("short_term", {}).get("structure", "unknown"),
            "vol_regime": pr_ctx.get("market_state", {}).get("short_term", {}).get("risk", "unknown"),
            "distance_to_key_level_pct": pr_ctx.get("market_state", {}).get("micro_term", {}).get("state", "unknown")
        }

        crowd_context = {
            "crowding_level": pr_ctx.get("crowd_state", {}).get("crowding_level", "unknown"),
            "funding_pressure": pr_ctx.get("crowd_state", {}).get("funding_pressure", "unknown"),
            "fragility": pr_ctx.get("crowd_state", {}).get("fragility", "unknown"),
            "bias": pr_ctx.get("crowd_state", {}).get("bias", "unknown")
        }

        ts_now = int(time.time() * 1000)

        # 3. 内部辅助函数：构建单个 Query
        async def build_query(position_snapshot: Dict):
            state = await reduce_temporal_state(
                exchange=exchange,
                trade_id=position_snapshot.get("trade_id", "sim"),
                symbol=symbol,
                position_side=position_snapshot.get("position_side", "LONG"),
                verdict=verdict,
                entry_ts=int(position_snapshot.get("entry_ts", 0)),
                event_ts=ts_now,
            )

            rc = RedisClient()
            last_suggestion_key = f"agent_output:position_risk:{exchange}:{symbol}:latest"
            last_suggestion_str = await rc.get(last_suggestion_key)
            last_action = "HOLD"
            last_action_ts = 0
            if last_suggestion_str:
                try:
                    ls = json.loads(last_suggestion_str)
                    payload = ls.get("payload", ls)
                    last_action = payload.get("recommended_action", "HOLD")
                    last_action_ts = int(ls.get("ts", 0))
                except:
                    pass

            minutes_since_last = (ts_now - last_action_ts) / 1000 / 60 if last_action_ts > 0 else 9999

            operational_context = {
                "risk_limits": {
                    "max_loss_pct": -0.06,
                    "max_holding_min": 0,
                    "max_exposure_pct": 1.0,
                    "cooldown_after_invalid_min": 0
                },
                "portfolio_context": {
                    "risk_mode": "normal",
                    "available_exposure_pct": 0.12,
                    "allow_add_position": True
                },
                "action_state": {
                    "last_action": last_action,
                    "last_action_min_ago": minutes_since_last,
                    "recent_action_count": 0,
                    "cooldown_active": False
                },
                "system_mode": {
                    "mode": "advisory",
                    "allow_reverse": True
                }
            }

            return {
                "symbol": symbol,
                "exchange": exchange,
                "ts_now": ts_now,
                "position_snapshot": position_snapshot,
                "signal_verdict": agent_output,
                "temporal_state": state,
                "market_context": market_context,
                "crowd_context": crowd_context,
                "operational_context": operational_context
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
        for q, r in zip(queries, parsed_results):
            pos_snapshot = q.get("position_snapshot", {})
            pos_side = pos_snapshot.get("position_side", "NONE")
            trade_id = pos_snapshot.get("trade_id")

            payload = r.get("payload", r)
            decision = payload.get("recommended_action", "HOLD")

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
            "step1_result": prev_result
        })
