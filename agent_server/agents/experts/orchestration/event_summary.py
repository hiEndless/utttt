from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
from agent_server.configs.prompts.event_summary import get_prompt
from agno.models.message import Message
import json
import time
from agent_server.agents.utils import (
    _json_dumps_safe,
    LLMOutputValidator,
    validate_with_retry,
)


class EventSummaryExpert:
    name = "event_summary"

    # Define Schema
    SCHEMA = {
        "symbol": {
            "type": str,
            "required": True,
            "description": "Trading symbol"
        },
        "review_verdict": {
            "type": str,
            "required": True,
            "options": ["SUCCESS", "FAILURE", "NEUTRAL", "PENDING"],
            "description": "Verdict of the event review"
        },
        "core_insight": {
            "type": str,
            "required": True,
            "description": "Core insight from the review"
        },
        "key_drivers": {
            "type": list,
            "required": True,
            "description": "Key drivers for the outcome"
        },
        "cognitive_adjustment": {
            "type": str,
            "required": True,
            "description": "Cognitive adjustment for future"
        },
        "market_state_review": {
            "type": str,
            "required": True,
            "description": "Review of the market state"
        },
        "notes": {
            "type": str,
            "required": False,
            "description": "Additional notes"
        }
    }

    def __init__(self, language: str = "zh"):
        self.validator = LLMOutputValidator(self.SCHEMA)
        self.language = language

    async def run(self, query: dict, exchange: str, symbol: str) -> str:

        cfg = get_agent_config(self.name)

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
                debug_mode=True,
            )
            return run_output.content

        try:
            final_result = await validate_with_retry(
                llm_runner=_run_llm,
                validator=self.validator,
                max_retries=3,
                on_retry=lambda msg: print(f"[EventSummaryExpert] {msg}")
            )
        except Exception as e:
            print(f"[EventSummaryExpert] Validation failed after retries: {e}")
            final_result = {
                "symbol": symbol,
                "review_verdict": "PENDING",
                "core_insight": f"Analysis failed: {str(e)}",
                "key_drivers": [],
                "cognitive_adjustment": "None",
                "market_state_review": "Unknown",
                "notes": "Validation failed"
            }

        ts = int(time.time() * 1000)
        if isinstance(final_result, dict):
            final_result["ts"] = ts
        else:
            final_result = {"data": final_result, "ts": ts}

        output = _json_dumps_safe(final_result)
        print(output)
        return output