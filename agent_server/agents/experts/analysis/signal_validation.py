from agent_server.configs.prompts.signal_validation import get_prompt
import json
import asyncio
from typing import Any, Dict

from agent_server.agents.experts.base_llm_expert import BaseLLMExpert, QueryInput


class SignalValidationExpert(BaseLLMExpert):
    name = "signal_validation"

    # Define Schema
    SCHEMA = {
        "verdict": {
            "type": str,
            "required": True,
            "options": ["VALID", "WEAK_VALID", "INVALID"],
            "description": "Validation verdict"
        },
        "alignment": {
            "type": str,
            "required": True,
            "options": ["ALIGNED", "CONFLICT", "STRONGLY_CONFLICT"],
            "description": "Structural alignment"
        },
        "confidence_adjustment": {
            "type": str,
            "required": True,
            "options": ["none", "down"],
            "description": "Confidence adjustment"
        },
        "reasoning": {
            "type": list,
            "required": True,
            "description": "List of structural reasons"
        }
    }

    def build_instructions(self, target_lang: str, **kwargs: Any) -> str:
        risk_mode = str(kwargs.get("risk_mode") or "normal")
        return get_prompt(target_lang, risk_mode)

    def build_fallback_result(self, error: Exception, query_obj: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return {
            "verdict": "INVALID",
            "alignment": "CONFLICT",
            "confidence_adjustment": "down",
            "reasoning": ["输出校验失败，已触发安全回退", str(error)],
        }

    async def run(self, query: QueryInput, risk_mode: str = "normal") -> str:
        return await super().run(query, risk_mode=risk_mode)


if __name__ == "__main__":
    from agent_server.agents.experts.analysis.utils.tf_validation import compute_tf_validation
    from agent_server.agent_context.builder import build_agent_context
    from agent_server.utils.redis_client import RedisClient
    from agent_server.agent_context.utils.crowd_interpreter import build_crowd_interpretation
    from agent_server.agent_context.utils.crowd_trend_analysis import enrich_and_clean_crowd_context

    final_signal = {"route": "indicators", "exchange": "binance", "symbol": "BTCUSDT", "final_priority": "low",
                    "event_id": "binance.BTCUSDT.trade.open.1768045518249", "market_state": "momentum", "direction": "bearish",
                    "confidence": "medium", "confidence_numeric": 0.5, "priority_weight": 10,
                    "l1_total_score": -56.91888, "tf_hint": ["15m", "30m", "1h"]}

    exchange = final_signal.get("exchange")
    symbol = final_signal.get("symbol")
    event_id = final_signal.get("event_id")
    direction = final_signal.get("direction")
    tf_hint = final_signal.get("tf_hint")
    tf_validation = compute_tf_validation(symbol, exchange, direction, tf_hint)

    expert = SignalValidationExpert()


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
        
        # Inject deterministic crowd interpretation (replaces raw crowd_positioning)
        interpretation = build_crowd_interpretation(full_context, direction)
        ctx["crowd_interpretation"] = interpretation
        
        ctx["crowd_state"], ctx["crowd_trend_analysis"] = await enrich_and_clean_crowd_context(
            exchange, symbol, ctx.get("crowd_state", {})
        )

        # print(ctx)

        query = {
            "symbol": symbol,
            "exchange": exchange,
            "event_id": event_id,
            "final_event": {
                "event_type": final_signal.get("route"),
                "direction": direction,
                "final_priority": final_signal.get("final_priority"),
                "confidence": final_signal.get("confidence"),
                "confidence_numeric": final_signal.get("confidence_numeric"),
                "tf_hint": tf_hint,
                "analysis_context": final_signal.get("analysis_context"),
            },
            "tf_validation": tf_validation,
            "context": ctx,
        }
        await expert.run(query)


    asyncio.run(_demo())
