from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
from agent_server.configs.prompts.signal_validation import prompt
from agno.models.message import Message
import json
import asyncio
import time
from agent_server.agents.experts.utils import (
    _extract_json_from_text,
    _ensure_json_serializable,
    _json_dumps_safe,
)
from agent_server.agent_context.output_store import save_agent_output


class SignalValidationExpert:
    name = "signal_validation"

    async def run(self, query: str) -> str:

        cfg = get_agent_config(self.name)

        model_id = cfg.get("model_id", "deepseek-ai/DeepSeek-V3")
        base_url = cfg.get("llm_base_url")
        api_key = cfg.get("llm_api_key")

        model = OpenAILike(id=model_id, base_url=base_url, api_key=api_key)

        agent = Agent(
            model=model,
            instructions=prompt,
        )

        run_output = await agent.arun(
            Message(role="user", content=json.dumps(query, ensure_ascii=False)),
            stream=False,
            debug_mode=True,
        )
        content = run_output.content
        if isinstance(content, str):
            try:
                final_result = json.loads(content)
            except json.JSONDecodeError:
                extracted = _extract_json_from_text(content)
                if extracted is not None:
                    final_result = extracted
                else:
                    final_result = {"raw": content}
        elif hasattr(content, "model_dump"):
            final_result = content.model_dump(exclude_none=True)
        else:
            final_result = content

        if isinstance(final_result, dict) and isinstance(final_result.get("raw"), str):
            extracted_raw = _extract_json_from_text(final_result["raw"])
            if extracted_raw is not None:
                final_result = extracted_raw

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
            await save_agent_output(self.name, exchange, symbol, ts, payload_obj, event_id=event_id)
        except Exception:
            pass

        output = _json_dumps_safe(final_result)
        print(output)
        return output


if __name__ == "__main__":
    from agent_server.tools.tf_validation import compute_tf_validation
    from agent_server.agent_context.builder import build_agent_context
    from agent_server.utils.redis_client import RedisClient

    final_signal = {"route": "indicators", "exchange": "binance", "symbol": "BTCUSDT", "final_priority": "low",
                    "event_id": "BTCUSDT.final.1767282634334", "market_state": "momentum", "direction": "bearish",
                    "confidence": "medium", "confidence_numeric": 0.5, "priority_weight": 10,
                    "l1_total_score": -56.91888, "tf_hint": ["15m", "30m", "1h"]}

    exchange = final_signal.get("exchange")
    symbol = final_signal.get("symbol")
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
        query = {
            "symbol": symbol,
            "exchange": exchange,
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
