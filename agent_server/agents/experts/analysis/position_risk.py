from agent_server.configs.prompts.position_risk import get_prompt
import json
import time
from typing import Any, Dict

from agent_server.agents.experts.base_llm_expert import BaseLLMExpert, QueryInput
from agent_server.utils.account import get_available_exposure_pct
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

    # Define Schema
    SCHEMA = {
    }

    def build_instructions(self, target_lang: str, **kwargs: Any) -> str:
        return get_prompt(target_lang)

    def build_fallback_result(self, error: Exception, query_obj: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return {
            "verdict": "CRITICAL",
            "suggestion": "HOLD",
            "reduce_pct": 0.0,
            "add_pct": 0.0,
            "tighten_stop": True,
            "freeze_add_position_min": 60,
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
    from agent_server.agent_context.utils.crowd_interpreter import build_crowd_interpretation
    from agent_server.agent_context.utils.crowd_trend_analysis import enrich_and_clean_crowd_context
    from agent_server.agents.experts.analysis.utils.execution_constraint_aggregator import ExecutionConstraintAggregator
    import asyncio

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
    exchange = meta.get("exchange")
    symbol = meta.get("symbol")

    position = get_position(exchange, symbol)[0]
    position_side = position["position_side"]
    trade_id = position.pop("trade_id")
    initialMargin = position.pop("initialMargin")  # 占用保证金，用于计算仓位占比

    expert = PositionRiskExpert()



    async def _demo():
        full_context = await output.build_output("binance", symbol)
        market_structure = build_agent_context("position_risk", full_context)
        # 打印裁剪后的 market_structure（用于验证 forbidden_* 裁剪是否生效）
        print(_json_dumps_safe(market_structure))



        # 4. 模拟 Operational Context (建议模式适配)
        # 从 Redis 获取上一次的建议记录，用于填充 action_state
        # rc = RedisClient()
        # last_suggestion_key = f"agent_output:{exchange}:{symbol}:position_risk:latest"
        # last_suggestion_str = await rc.get(last_suggestion_key)

        # 获取账户余额计算可用仓位比例
        calculated_available_pct = await get_available_exposure_pct(exchange)



        query = {
            "meta": meta,
            "market_structure": market_structure,
            "position": position,
            "account": "",
            "execution_constraint": execution_constraint,
        }

        # print("\n=== Agent Input Query ===")
        # print(json.dumps(query, indent=2, ensure_ascii=False))
        # print("=========================\n")

        # await expert.run(query)


    asyncio.run(_demo())
