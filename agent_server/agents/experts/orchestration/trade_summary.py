from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
from agent_server.configs.prompts.trade_summary import get_prompt
from agno.models.message import Message
import json
import time
from agent_server.agents.utils import (
    _json_dumps_safe,
    LLMOutputValidator,
    validate_with_retry,
)


class TradeSummaryExpert:
    name = "trade_summary"

    # Define Schema
    SCHEMA = {
        "symbol": {
            "type": str,
            "required": True,
            "description": "Trading symbol"
        },
        "position_side": {
            "type": str,
            "required": True,
            "options": ["LONG", "SHORT"],
            "description": "Position side"
        },
        "reasoning": {
            "type": list,
            "required": True,
            "description": "Detailed reasoning process (Audit Log)"
        },
        "trade_verdict": {
            "type": str,
            "required": True,
            "options": ["GOOD_TRADE", "BAD_TRADE", "GOOD_LOSS", "BAD_WIN"],
            "description": "Trade verdict"
        },
        "summary": {
            "type": dict,
            "required": True,
            "description": "Summary for long-term memory"
        }
    }

    def __init__(self, language: str = "zh"):
        self.validator = LLMOutputValidator(self.SCHEMA)
        self.language = language

    async def run(self, query: dict, exchange: str, symbol: str) -> str:

        cfg = get_agent_config(self.name)

        target_lang = cfg.get("language", self.language)

        model_id = str(cfg.get("model_id") or "").strip()
        base_url = str(cfg.get("llm_base_url") or "").strip() or None
        api_key = str(cfg.get("llm_api_key") or "").strip() or None
        missing_keys: list[str] = []
        if not model_id:
            missing_keys.append("model_id")
        if not base_url:
            missing_keys.append("llm_base_url")
        if not api_key:
            missing_keys.append("llm_api_key")
        if missing_keys:
            return _json_dumps_safe({"error": "agent_config_missing", "missing": missing_keys, "ts": int(time.time() * 1000)})

        model = OpenAILike(id=model_id, base_url=base_url, api_key=api_key)

        agent = Agent(
            model=model,
            instructions=get_prompt(target_lang),
        )

        async def _run_llm():
            run_output = await agent.arun(
                Message(role="user", content=json.dumps(query, ensure_ascii=False)),
                stream=False,
                debug_mode=True,
            )
            return run_output.content

        try:
            final_result = await validate_with_retry(
                llm_runner=_run_llm,
                validator=self.validator,
                max_retries=3,
                on_retry=lambda msg: print(f"[TradeSummaryExpert] {msg}")
            )
        except Exception as e:
            print(f"[TradeSummaryExpert] Validation failed after retries: {e}")
            final_result = {
                "symbol": symbol,
                "position_side": "LONG",  # Default, hard to guess
                "reasoning": ["输出校验失败，已触发安全回退", str(e)],
                "trade_verdict": "BAD_TRADE", # Fail-safe verdict
                "summary": {
                    "trade_overview": "Analysis failed due to validation errors.",
                    "execution_consistency": "Unknown",
                    "event_alignment": "Unknown",
                    "key_observations": [],
                    "notable_deviations": []
                }
            }

        ts = int(time.time() * 1000)
        if isinstance(final_result, dict):
            final_result["ts"] = ts
        else:
            final_result = {"data": final_result, "ts": ts}

        output = _json_dumps_safe(final_result)
        print(output)
        return output
