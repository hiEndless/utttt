from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
from agent_server.configs.prompts.signal_validation import get_prompt
from agno.models.message import Message
import json
import asyncio
import time
from agent_server.agents.utils import (
    _json_dumps_safe,
    LLMOutputValidator,
    validate_with_retry,
)
from agent_server.agent_context.output_store import save_agent_output


class SignalValidationExpert:
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

    def __init__(self, language: str = "zh"):
        self.validator = LLMOutputValidator(self.SCHEMA)
        self.language = language

    async def run(self, query: str) -> str:

        cfg = get_agent_config(self.name)
        
        # 优先从环境变量/配置获取，其次使用实例属性
        target_lang = cfg.get("language", self.language)

        model_id = cfg.get("model_id", "deepseek-ai/DeepSeek-V3")
        base_url = cfg.get("llm_base_url")
        api_key = cfg.get("llm_api_key")

        model = OpenAILike(id=model_id, base_url=base_url, api_key=api_key)

        agent = Agent(
            model=model,
            instructions=get_prompt(target_lang),
        )

        async def _run_llm():
            run_output = await agent.arun(
                Message(role="user", content=json.dumps(query, ensure_ascii=False)),
                stream=False,
                debug_mode=False,
            )
            return run_output.content

        try:
            final_result = await validate_with_retry(
                llm_runner=_run_llm,
                validator=self.validator,
                max_retries=3,
                on_retry=lambda msg: print(f"[SignalValidationExpert] {msg}")
            )
        except Exception as e:
            print(f"[SignalValidationExpert] Validation failed after retries: {e}")
            final_result = {
                "verdict": "INVALID",
                "alignment": "CONFLICT",
                "confidence_adjustment": "down",
                "reasoning": ["validation_failed", str(e)]
            }

        # 构建产出物系统数据结构
        try:
            qobj = json.loads(query) if isinstance(query, str) else (query or {})
        except Exception:
            qobj = {}
        symbol = qobj.get("symbol") or "UNKNOWN"
        exchange = qobj.get("exchange") or "binance"
        event_id = qobj.get("event_id")
        ts = int(time.time() * 1000)

        try:
            payload_obj = final_result if isinstance(final_result, dict) else json.loads(str(final_result))
        except Exception:
            payload_obj = {"raw": final_result}
        try:
            await save_agent_output(self.name, exchange, symbol, ts, payload_obj, event_id=event_id, model_id=model_id)
        except Exception:
            pass

        output = _json_dumps_safe(final_result)
        print(output)
        return output


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
