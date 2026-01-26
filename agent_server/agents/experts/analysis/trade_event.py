from agent_server.configs.prompts.trade_event import get_prompt
import json
import asyncio
from typing import Any, Dict

from agent_server.agents.experts.base_llm_expert import BaseLLMExpert, QueryInput


class TradeEventExpert(BaseLLMExpert):
    name = "trade_event"

    # Define schema for LLM output validation
    SCHEMA = {
        "verdict": {
            "type": str,
            "required": True,
            "options": ["VALID", "WEAK_VALID", "INVALID"],
            "description": "裁决结果：VALID(有效) | WEAK_VALID(弱有效) | INVALID(无效)"
        },
        "alignment": {
            "type": str,
            "required": True,
            "options": ["ALIGNED", "CONFLICT", "STRONGLY_CONFLICT"],
            "description": "结构一致性：ALIGNED(一致) | CONFLICT(冲突) | STRONGLY_CONFLICT(严重冲突)"
        },
        "confidence_adjustment": {
            "type": str,
            "required": True,
            "options": ["none", "down"],
            "description": "可信度调整：none(无) | down(下调)"
        },
        "reasoning": {
            "type": list,
            "required": True,
            "description": "结构性原因列表（通常包含3点）"
        }
    }

    def build_instructions(self, target_lang: str, **kwargs: Any) -> str:
        return get_prompt(target_lang)

    def build_llm_input(self, query_obj: Dict[str, Any], **kwargs: Any) -> Any:
        trade_core = query_obj.get("trade_core", {})
        position_effect = query_obj.get("position_effect", {})
        position_context = query_obj.get("position_context", {})
        context_data = query_obj.get("context", {})
        return {
            "trade_core": trade_core,
            "position_effect": position_effect,
            "position_context": position_context,
            **(context_data or {}),
        }

    def build_fallback_result(self, error: Exception, query_obj: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return {
            "error": str(error),
            "verdict": "INVALID",
            "alignment": "CONFLICT",
            "confidence_adjustment": "down",
            "reasoning": ["输出校验失败，已触发安全回退"],
        }

    async def run(self, query: QueryInput) -> str:
        return await super().run(query)


if __name__ == "__main__":
    from agent_server.agents.experts.analysis.utils.trade_core_data import abstract_trade_event
    from agent_server.agent_context.builder import build_agent_context
    from agent_server.utils.redis_client import RedisClient
    from agent_server.agent_context.utils.crowd_interpreter import build_crowd_interpretation
    from agent_server.agent_context.utils.crowd_trend_analysis import enrich_and_clean_crowd_context

    final_signal = {'route': 'trade', 'exchange': 'binance', 'symbol': 'ETHUSDT', 'final_priority': 'low',
                    'event_id': 'binance.ETHUSDT.trade.open.1768803852754', 'event_type': 'trade.open',
                    'timestamp': '1768803852754', 'market_state': None, 'direction': None, 'confidence': None,
                    'confidence_numeric': None, 'priority_weight': None, 'l1_total_score': None, 'tf_hint': None,
                    'analysis_context': {}, 'meta': {'source_event_id': 'binance.ETHUSDT.trade.open.1768803852754',
                                                     'origin_source_hint': 'trade', 'is_short_term': False},
                    'trade_details': {'trade_id': 'e95cbad77cde4d8e80d405d1ff9a6f5f', 'position_side': 'SHORT',
                                      'current_size': '-0.007', 'entry_price': '3193.0', 'mark_price': '3193.00000000',
                                      'pnl_ratio': '0.0', 'action': 'OPEN', 'change_amount': '-0.007'}}

    exchange = final_signal.get("exchange")
    symbol = final_signal.get("symbol")
    event_id = final_signal.get("event_id")
    direction = final_signal.get("direction")
    trade_details = final_signal.get("trade_details")
    trade_core = abstract_trade_event(trade_details)

    expert = TradeEventExpert()

    async def _read_market_state(ex: str, sym: str):
        rc = RedisClient()
        key = f"background:{ex}:{sym}:market_state"
        v = await rc.get(key)
        try:
            return json.loads(v or "{}") if v else {}
        except Exception:
            return {}

    async def _demo():
        bg = await _read_market_state(exchange, symbol)
        full_context = bg if isinstance(bg, dict) and bg else {"symbol": symbol, "ts": 0, "market_state": {},
                                                               "crowd_state": {}}
        ctx = build_agent_context("signal_validation", full_context)
        
        # Inject deterministic crowd interpretation
        position_side = trade_details.get("position_side", "flat")
        interpretation = build_crowd_interpretation(full_context, position_side)
        ctx["crowd_interpretation"] = interpretation

        ctx["crowd_state"], ctx["crowd_trend_analysis"] = await enrich_and_clean_crowd_context(
            exchange, symbol, ctx.get("crowd_state", {})
        )
        
        query = {
            "symbol": symbol,
            "exchange": exchange,
            "event_id": event_id,
            "trade_core": trade_core,
            "context": ctx,
        }
        await expert.run(query)


    asyncio.run(_demo())
