import asyncio
import time
import json
from typing import Any, Dict

from agent_server.agent_context.market_structure import output
from agent_server.agent_context.output_store import save_agent_output
from agent_server.agents.experts.base_llm_expert import BaseLLMExpert, QueryInput
from agent_server.agents.utils import _json_dumps_safe
from agent_server.configs.prompts.signal_validation import get_prompt
from agent_server.configs.source import get_agent_config


class SignalValidationExpert(BaseLLMExpert):
    """
    “已有方向信号，在当前多周期结构背景下是否自洽 / 是否存在硬性结构冲突”的审计器
    """
    name = "signal_validation"
    version = "v1.0"

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
        return get_prompt(target_lang)

    def build_fallback_result(self, error: Exception, query_obj: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return {
            "verdict": "BLOCK",
            "structural_alignment": "STRONG_CONFLICT",
            "risk_implication": "elevated",
            "reasoning": ["输出校验失败，已触发安全回退", str(error)],
        }

    async def run(self, query: QueryInput, **kwargs: Any) -> str:
        cfg = get_agent_config(self.name)
        target_lang = cfg.get("language", self.language)

        model_id = cfg.get("model_id", "deepseek-ai/DeepSeek-V3")
        base_url = cfg.get("llm_base_url")
        api_key = cfg.get("llm_api_key")

        instructions = self.build_instructions(target_lang, **kwargs)
        agent = self._build_agent(model_id=model_id, base_url=base_url, api_key=api_key, instructions=instructions)

        qobj = self._parse_query(query)
        meta = qobj.pop("meta", {}) or {}
        positions = qobj.pop("positions",  []) or []
        # 将 meta 也传递给 LLM，但仍保持 qobj 作为业务字段集合，便于后续落库与默认值回退
        llm_query_obj = dict(qobj)
        llm_input = self.build_llm_input(llm_query_obj, **kwargs)

        try:
            final_result = await self._run_validated(
                agent=agent,
                llm_input=llm_input,
                on_retry=lambda msg: print(f"[{self.__class__.__name__}] {msg}"),
                max_retries=3,
            )
        except Exception as e:
            print(f"[{self.__class__.__name__}] Validation failed after retries: {e}")
            final_result = self.build_fallback_result(e, qobj, **kwargs)

        try:
            final_result = self.postprocess_result(final_result, qobj, **kwargs)
        except Exception:
            pass

        symbol = qobj.get("symbol") or meta.get("symbol") or "UNKNOWN"
        exchange = qobj.get("exchange") or meta.get("exchange") or "binance"
        event_id = qobj.get("event_id") or meta.get("event_id")
        trade_id = qobj.get("trade_id") or meta.get("trade_id")
        meta["ts"] = int(time.time() * 1000)
        meta["version"] = self.version

        payload_obj: Dict[str, Any]
        try:
            payload_obj = final_result if isinstance(final_result, dict) else json.loads(str(final_result))
        except Exception:
            payload_obj = {"raw": final_result}

        try:
            payload_obj = self.normalize_for_storage(payload_obj, qobj, **kwargs)
        except Exception:
            pass
        payload_obj["meta"] = meta
        payload_obj["positions"] = positions

        try:
            await save_agent_output(
                self.name,
                exchange,
                symbol,
                meta["ts"],
                payload_obj,
                event_id=event_id,
                trade_id=trade_id,
                model_id=model_id,
            )
        except Exception:
            pass

        # 返回给调用方的结果也补充 meta（包含 ts/version），避免下游需要额外查存储
        result_for_return: Dict[str, Any]
        if isinstance(final_result, dict):
            result_for_return = dict(final_result)
        else:
            result_for_return = {"raw": final_result}
        result_for_return["meta"] = meta
        result_for_return["positions"] = positions
        output = _json_dumps_safe(result_for_return)
        print(output)
        return output


if __name__ == "__main__":
    from agent_server.tools.get_position import get_position
    from agent_server.agents.experts.analysis.utils.signal_cropper import crop_signal
    from agent_server.agent_context.builder import build_agent_context
    from agent_server.agent_context.market_structure.holding_context_from_positions import (
        build_holding_context_from_positions,
    )
    from agent_server.utils.redis_client import RedisClient

    final_signal = {"route": "mixed", "exchange": "binance", "symbol": "ETHUSDT", "final_priority": "low",
                    "event_id": "ETHUSDT.final.1770290252305", "event_type": "market.structure",
                    "timestamp": "1770290252305", "market_state": "momentum", "direction": "bullish",
                    "confidence": "medium", "confidence_numeric": 0.5, "priority_weight": 10,
                    "l1_total_score": 19.668839999999996, "tf_hint": ["15m", "30m", "1h"],
                    "analysis_context": {"dominant_bucket": "mid", "supporting_buckets": ["mid"],
                                         "tf_hint": ["15m", "30m", "1h"], "l1_total_score": 19.668839999999996,
                                         "bias": {"short": False, "mid": True}, "reason_tags": ["high_structure_score"],
                                         "lock_window_sec": 900, "provenance": {
                            "origin_sources": ["alerts_consumer", "force_stats_consumer", "ind_event_engine"],
                            "origin_source_hint": "mixed"}, "_debug": {
                            "scores": {"bucket_short": "0.0", "bucket_mid": "19.668839999999996", "bucket_long": "0.0"},
                            "dirs": {"short": "neutral", "mid": "bullish", "long": "neutral"},
                            "component_scores": {"momentum": 19.668839999999996}, "indicators": [
                                {"plugin": "single_signal_williams_r", "cls": "momentum", "dir": "bullish",
                                 "score": 2.9599999999999995, "bucket": "mid", "priority": "medium"},
                                {"plugin": "single_signal_williams_r", "cls": "momentum", "dir": "bullish",
                                 "score": 2.7079999999999997, "bucket": "mid", "priority": "medium"},
                                {"plugin": "depth.liquidity_collapse", "cls": "unknown", "dir": "neutral", "score": 4.0,
                                 "bucket": "short", "priority": "low"},
                                {"plugin": "single_signal_williams_r", "cls": "momentum", "dir": "bullish",
                                 "score": 3.14, "bucket": "mid", "priority": "high"},
                                {"plugin": "force_spike_sell", "cls": "unknown", "dir": "neutral",
                                 "score": 0.3333333333333333, "bucket": "short", "priority": "low"},
                                {"plugin": "single_signal_williams_r", "cls": "momentum", "dir": "bullish",
                                 "score": 2.9672, "bucket": "mid", "priority": "medium"},
                                {"plugin": "single_signal_williams_r", "cls": "momentum", "dir": "bullish",
                                 "score": 3.0644, "bucket": "mid", "priority": "high"}]}},
                    "meta": {"grader_version": "1.2.0",
                             "source_event_id": "binance.binance_public.ETHUSDT.single_signal_williams_r.1770290252305",
                             "ts_unit": "ms", "min_interval_sec": 900, "origin_source_hint": "mixed",
                             "origin_sources": ["alerts_consumer", "force_stats_consumer", "ind_event_engine"]},
                    "trade_details": {}}

    # 信号裁剪
    cropped_signal = crop_signal(final_signal)
    # print(cropped_signal)

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
                "direction": direction
            },
            "positions": positions,
            "final_event": cropped_signal,
            "context": ctx,
        }
        await expert.run(query)


    asyncio.run(_demo())
