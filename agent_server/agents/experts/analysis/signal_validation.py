from agent_server.configs.prompts.signal_validation import get_prompt
import json
import asyncio
from typing import Any, Dict
from agent_server.agent_context.market_structure import output
from agent_server.agents.experts.base_llm_expert import BaseLLMExpert, QueryInput


class SignalValidationExpert(BaseLLMExpert):
    """
    “已有方向信号，在当前多周期结构背景下是否自洽 / 是否存在硬性结构冲突”的审计器
    """
    name = "signal_validation"

    # Define Schema
    SCHEMA = {
      "verdict": {
        "type": str,
        "options": ["ALLOW", "ATTENUATE", "BLOCK"],
        "description": "Whether the signal is allowed to propagate under current structure"
      },
      "structural_alignment": {
        "type": str,
        "options": ["ALIGNED", "PARTIAL_CONFLICT", "STRONG_CONFLICT"],
        "description": "Degree of structural consistency between signal direction and multi-horizon context"
      },
      "risk_implication": {
        "type": str,
        "options": ["none", "elevated"],
        "description": "Structural risk implication implied by conflicts"
      },
      "reasoning": {
        "type": list,
        "description": "Concrete structural conflict or support points"
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
    from agent_server.tools.get_position import get_position
    from agent_server.agents.experts.analysis.utils.signal_cropper import crop_signal
    from agent_server.agent_context.builder import build_agent_context
    from agent_server.agent_context.market_structure.holding_context_from_positions import (
        build_holding_context_from_positions,
    )
    from agent_server.utils.redis_client import RedisClient

    final_signal = {"route": "indicators", "exchange": "binance", "symbol": "RIVERUSDT", "final_priority": "low",
                    "event_id": "ETHUSDT.final.1770232087150", "event_type": "market.structure",
                    "timestamp": "1770232087150", "market_state": "momentum", "direction": "bullish",
                    "confidence": "medium", "confidence_numeric": 0.5, "priority_weight": 10, "l1_total_score": 8.19,
                    "tf_hint": ["15m", "30m", "1h"],
                    "analysis_context": {"dominant_bucket": "mid", "supporting_buckets": ["mid"],
                                         "tf_hint": ["15m", "30m", "1h"], "l1_total_score": 8.19,
                                         "bias": {"short": False, "mid": True}, "reason_tags": ["high_structure_score"],
                                         "lock_window_sec": 900, "provenance": {"origin_sources": ["ind_event_engine"],
                                                                                "origin_source_hint": "indicators"},
                                         "_debug": {"scores": {"bucket_short": "0.0", "bucket_mid": "8.19",
                                                               "bucket_long": "0.0"},
                                                    "dirs": {"short": "neutral", "mid": "bullish", "long": "neutral"},
                                                    "component_scores": {"volatility": 8.19}, "indicators": [
                                                 {"plugin": "single_signal_boll", "cls": "volatility", "dir": "bullish",
                                                  "score": 5.46, "bucket": "mid", "priority": "high"}]}},
                    "meta": {"grader_version": "1.2.0",
                             "source_event_id": "binance.binance_public.ETHUSDT.single_signal_boll.1770232087150",
                             "ts_unit": "ms", "min_interval_sec": 900, "origin_source_hint": "indicators",
                             "origin_sources": ["ind_event_engine"]}, "trade_details": {}}
    
    # 信号裁剪
    cropped_signal = crop_signal(final_signal)

    exchange = final_signal.get("exchange")
    symbol = final_signal.get("symbol")
    event_id = final_signal.get("event_id")
    direction = final_signal.get("direction")

    expert = SignalValidationExpert()

    # 获取持仓，计算持仓时间，裁剪周期桶背景
    positions = get_position(exchange, symbol)
    holding_context = build_holding_context_from_positions(positions)
    holding_horizon = holding_context.get("horizon")


    async def _read_market_state(ex: str, sym: str):
        rc = RedisClient()
        key = f"background:{ex}:{sym}:market_state"
        v = await rc.get(key)
        try:
            return json.loads(v or "{}") if v else {}
        except Exception:
            return {}


    async def _demo():
        full_context = await output.build_output("binance", symbol)
        ctx = build_agent_context("signal_validation", full_context, horizon=holding_horizon)
        # print(ctx)

        query = {
            "meta": {
                "symbol": symbol,
                "exchange": exchange,
                "event_id": event_id,
                "event_type": final_signal.get("route"),
            },

            "final_event": cropped_signal,
            "context": ctx,
        }
        await expert.run(query)


    asyncio.run(_demo())
