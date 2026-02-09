from agent_server.configs.prompts.position_risk import get_prompt
import json
import time
from typing import Any, Dict

from agent_server.agents.experts.base_llm_expert import BaseLLMExpert, QueryInput
from agent_server.utils.account import account_state
from agent_server.config import settings
from agent_server.risk.action_policy import enforce_position_risk_action
from agent_server.agent_context.market_structure import output
from agent_server.agents.utils import (
    _ensure_json_serializable,
    _json_dumps_safe,
    LLMOutputValidator,
    validate_with_retry,
)


class PositionRiskExpert(BaseLLMExpert):
    name = "position_risk"
    version = "v1.0"

    # 中文注释：LLM 输出严格 schema（与 prompts/position_risk.py 的“输出要求”一致）
    SCHEMA = {
        "risk_action": {
            "type": "string",
            "options": ["hold", "reduce", "scale_in_small", "exit"],
            "required": True,
            "description": "风控动作：hold/reduce/scale_in_small/exit",
        },
        "exposure_delta": {
            "type": "object",
            "required": True,
            "description": "相对当前仓位的变化比例（percentage）",
            "schema": {
                "type": {
                    "type": "string",
                    "options": ["percentage"],
                    "required": True,
                },
                "value": {
                    "type": "number",
                    "required": True,
                    "range": (-1.0, 1.0),
                },
            },
        },
        "reasoning": {
            "type": "array",
            "required": True,
            "description": "2-5条事实+结构/约束驱动理由（中文）",
        },
    }

    def build_instructions(self, target_lang: str, **kwargs: Any) -> str:
        return get_prompt(target_lang)

    def build_fallback_result(self, error: Exception, query_obj: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        # 中文注释：校验失败时返回保守“持有”，并补齐 execution_state 所需字段
        return {
            "risk_action": "hold",
            "exposure_delta": {"type": "percentage", "value": 0.0},
            "reasoning": ["输出校验失败，已触发安全回退", str(error)],
        }

    def postprocess_result(self, result: Dict[str, Any], query_obj: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        risk_rules_decision = query_obj.get("risk_rules_decision") or {}
        available_pct = (
            (query_obj.get("operational_context") or {})
            .get("portfolio_context", {})
            .get("available_exposure_pct")
        )
        final_result, _ = enforce_position_risk_action(
            llm_output=result if isinstance(result, dict) else {},
            risk_rules_decision=risk_rules_decision,
            available_exposure_pct=available_pct,
        )
        return final_result

    async def run(self, query: QueryInput) -> str:
        return await super().run(query)


if __name__ == "__main__":
    from agent_server.reducers.position_risk_decider import decide_position_action
    from agent_server.tools.get_position import get_position
    from agent_server.utils.redis_client import RedisClient
    from agent_server.agent_context.builder import build_agent_context
    from agent_server.agent_context.market_structure.holding_context import build_holding_context
    from agent_server.agent_context.utils.crowd_trend_analysis import enrich_and_clean_crowd_context
    from agent_server.agents.experts.analysis.utils.execution_constraint_aggregator import ExecutionConstraintAggregator
    import asyncio
    from agent_server.risk.execution_state_aggregator import aggregate_execution_state_and_store

    sv_out = {"verdict": "ATTENUATE", "structural_alignment": "PARTIAL_CONFLICT", "risk_implication": "elevated",
              "reasoning": ["多周期结构存在轻度冲突，建议降低仓位与加仓强度"],
              "meta": {"symbol": "ETHUSDT", "exchange": "binance", "event_id": "ETHUSDT.final.1770290252305",
                       "event_type": "mixed", "ts": 1770304117868, "version": "v1.0", "direction": "bullish"}}

    d_out = {"trade_intent_range": {"allowed_actions": ["hold", "reduce", "scale_in_small"],
                                    "forbidden_actions": ["aggressive_add", "reverse_position"],
                                    "risk_bias": "conservative"},
             "decision_rationale": ["4h/1d 结构偏多但短周期流动性不稳，建议保守执行"],
             "meta": {"symbol": "ETHUSDT", "exchange": "binance", "event_id": "ETHUSDT.final.1770290252305",
                      "event_type": "mixed", "ts": 1770408041105, "version": "v1.0", "direction": "bullish",
                      "trade_id": "9cedf3d0770041c8b11856c35ef664a2"}}

    execution_constraint = ExecutionConstraintAggregator().aggregate(sv_out, d_out).get("execution_constraint")
    meta = d_out.get("meta")
    trade_id = meta.get("trade_id")
    exchange = meta.get("exchange")
    symbol = meta.get("symbol")

    positions = get_position(exchange, symbol)
    position = {}
    for p in positions:
        if p["trade_id"] == trade_id:
            horizon = build_holding_context(p["open_time"], int(time.time() * 1000)).get("horizon")
            position = {
                "position_side": p["position_side"],
                "size": p["size"],
                "notional": p["notional"],
                "pnl_ratio": p["pnl_ratio"],
                "holding_duration": horizon.split("_")[0],
            }
            initialMargin = float(p.pop("initialMargin", 0))  # 占用保证金，用于计算仓位占比
            break
    # print(position)

    expert = PositionRiskExpert()


    async def _demo():
        full_context = await output.build_output("binance", symbol)
        market_structure = build_agent_context("position_risk", full_context)
        # 打印裁剪后的 market_structure（用于验证 forbidden_* 裁剪是否生效）
        # print(_json_dumps_safe(market_structure))

        # 从 Redis 获取上一次的建议记录，用于填充 action_state
        # rc = RedisClient()
        # last_suggestion_key = f"agent_output:{exchange}:{symbol}:position_risk:latest"
        # last_suggestion_str = await rc.get(last_suggestion_key)

        # 获取账户余额计算可用仓位比例
        account_risk_state = await account_state(exchange)
        account_risk_state["position_occupancy_ratio"] = initialMargin / account_risk_state.get("balance", 1)

        query = {
            "meta": meta,
            "market_structure": market_structure,
            "position": position,
            "account_risk_state": account_risk_state,
            "execution_constraint": execution_constraint,
        }
        # print( query)

        # print("\n=== Agent Input Query ===")
        # print(json.dumps(query, indent=2, ensure_ascii=False))
        # print("=========================\n")

        # 中文注释：等待 LLM 输出完成后再返回
        raw = await expert.run(query)
        return json.loads(raw)


    # out_put = asyncio.run(_demo())

    async def _execution():
        out_put = await _demo()
        # 生成仓位风控状态
        execution_state = await aggregate_execution_state_and_store(
            risk_action_output=out_put,
            signal_validation_output=sv_out,
            previous_execution_state=None,
            now_ts=int(time.time() * 1000),
            exchange=exchange,
            trade_id=trade_id,
            symbol=symbol,
        )
        print(json.dumps(execution_state, ensure_ascii=False))


    asyncio.run(_execution())
