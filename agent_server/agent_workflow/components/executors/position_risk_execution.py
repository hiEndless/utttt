import asyncio
import json
import time
from typing import Dict, Optional, List
from agno.workflow import StepInput
from agent_server.tools.get_position import get_position
from agent_server.reducers.temporal_state_reducer import reduce_temporal_state
from agent_server.reducers.position_risk_decider import decide_position_action
from agent_server.utils.redis_client import RedisClient
from agent_server.agent_context.builder import build_agent_context
from agent_server.agent_context.utils.crowd_interpreter import build_crowd_interpretation
from agent_server.agent_context.utils.crowd_trend_analysis import enrich_and_clean_crowd_context
from agent_server.agents.experts.analysis.position_risk import PositionRiskExpert
from agent_server.agent_workflow.components.base import BaseWorkflowComponent
from agent_server.utils.account import get_available_exposure_pct
from agent_server.config import settings
from agent_server.risk.action_policy import derive_allowed_llm_policy


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
        prev_output = prev_result["output"]
        full_context = prev_result["full_context"]
        # 判断是否有skipped字段
        if prev_output.get("skipped"):
            print(f"--- 持仓风控跳过：{event_data.get('symbol')} (Previous Skipped) ---")
            return self._safe_json_dumps(prev_output)

        symbol = event_data.get("symbol")
        exchange = event_data.get("exchange")
        
        print(f"--- 持仓风控执行：{symbol} ---")

        # 1. 获取持仓
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
        agent_output = prev_output.get("agent_output", prev_output)
        verdict = agent_output.get("verdict", "UNKNOWN")
        alignment = agent_output.get("alignment")
        
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

        crowd_context, crowd_trend_analysis = await enrich_and_clean_crowd_context(exchange, symbol, crowd_context)

        # 3. 内部辅助函数：构建单个 Query
        async def build_query(position_snapshot: Dict):
            trade_id = position_snapshot.get("trade_id")
            pos_side = position_snapshot.get("position_side", "LONG")
            
            # Position-aware Context Injection
            # 为当前处理的持仓方向生成专属的解释
            interpretation = build_crowd_interpretation(context_to_use, pos_side)
            pr_ctx["crowd_interpretation"] = interpretation

            # Re-extract Crowd Context from injected interpretation
            # 此时 crowd_context 已经是“顺风/逆风”等结论性描述
            injected_crowd = pr_ctx.get("crowd_interpretation", {})

            state = await reduce_temporal_state(
                exchange=exchange,
                trade_id=trade_id or "sim",
                symbol=symbol,
                position_side=pos_side,
                verdict=verdict,
                alignment=alignment,
                entry_ts=int(position_snapshot.get("entry_ts", 0)),
                event_ts=ts_now,
            )

            # Load user specific config from DB here (TODO)
            user_config = {}
            risk_cfg = {**settings.risk_defaults, **user_config}

            decision_rules = decide_position_action(
                holding_duration_min=state["holding_duration_min"],
                # 使用 reducer 计算的“距上一次事件时间”，避免 last_update_ts 刚覆盖导致恒为 0
                time_since_last_event_min=int(state.get("time_since_last_event_min", 0) or 0),
                valid_streak=state["valid_streak"],
                invalid_streak=state["invalid_streak"],
                conflict_streak=state["conflict_streak"],
                risk_mode=risk_cfg["risk_mode"]  # 动态传入 risk_mode
            )

            # 将硬规则动作集合投影到 LLM 输出动作集合，降低 LLM 选错动作的概率
            llm_policy = derive_allowed_llm_policy(decision_rules)
            decision_rules["allowed_actions_llm"] = sorted(llm_policy.allowed_llm_actions)
            if llm_policy.max_add_pct is not None:
                decision_rules["max_add_pct"] = llm_policy.max_add_pct
            if llm_policy.forbid_add:
                decision_rules["forbid_add"] = True

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

            calculated_available_pct = await get_available_exposure_pct(exchange)

            operational_context = {
                "risk_limits": {
                    "max_loss_pct": risk_cfg["max_loss_pct"],  # 最大亏损百分比 (建议参考值) 用户设置
                    "max_holding_min": risk_cfg["max_holding_min"],  # 最长持仓时间 (0 表示不限制，由上游策略决定)
                    "cooldown_after_invalid_min": risk_cfg["cooldown_after_invalid_min"]  # 建议模式下设为 0，保持对风险的实时敏感度
                },
                "portfolio_context": {
                    "risk_mode": risk_cfg["risk_mode"],  # 账户风险模式: normal | conservative | aggressive
                    "available_exposure_pct": calculated_available_pct,  # 剩余可用仓位
                    "allow_add_position": risk_cfg["allow_add_position"]  # 是否允许加仓 (根据资金情况)
                },
                "action_state": {
                    "last_action": last_action,  # 使用上一次的“建议”作为 last_action
                    "last_action_min_ago": minutes_since_last,
                    "recent_action_count": 0,  # 建议模式下可忽略频次限制
                    "cooldown_active": False  # 建议模式下关闭冷却，允许随时输出最新建议
                },
                "system_mode": {
                    "mode": risk_cfg["system_mode"],  # 标记为建议/顾问模式 系统整体模式: normal | defensive | recovery
                    "allow_reverse": risk_cfg["allow_reverse"]  # 允许灵活调整观点
                }
            }

            return {
                "symbol": symbol,
                "exchange": exchange,
                "event_id": event_data.get("event_id"),
                "trade_id": trade_id,
                "ts_now": ts_now,
                "position_snapshot": position_snapshot,
                "signal_verdict": agent_output,
                "temporal_state": state,
                "risk_rules_decision": decision_rules,
                "market_context": market_context,
                "crowd_context": crowd_context,
                "crowd_interpretation": injected_crowd,
                "crowd_trend_analysis": crowd_trend_analysis,
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
