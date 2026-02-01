from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
from agent_server.agent_context.market_structure import output
from agent_server.agent_context.builder import build_agent_context
from agent_server.configs.prompts.market_structure import prompt
from agno.models.message import Message
import json
import asyncio
from agent_server.utils.redis_client import RedisClient
import time
from agent_server.agents.utils import (
    _ensure_json_serializable,
    _json_dumps_safe,
    LLMOutputValidator,
    validate_with_retry,
)


class MarketStructureExpert:
    """
    系统认知层
    市场结构描述，使用同样的模型分析。用于人类可读，复盘方便。
    非口语化描述，不掺杂“隐含判断”或“因果推断”
    系统记忆的一部分。
    复盘时需要严格排除interpretive_overlay字段
    """
    version = "v1.0"
    name = "market_structure"

    # Define Schema
    SCHEMA = {
    }

    def __init__(self):
        self.validator = LLMOutputValidator(self.SCHEMA)

    async def run(self, query: dict) -> str:
        meta = {
            "symbol": query["symbol"],
            "ts": query["ts"],
            "version": self.version,
          }

        cfg = get_agent_config(self.name)

        model_id = cfg.get("model_id", "deepseek-ai/DeepSeek-V3")
        base_url = cfg.get("llm_base_url")
        api_key = cfg.get("llm_api_key")

        model = OpenAILike(id=model_id, base_url=base_url, api_key=api_key)

        agent = Agent(
            model=model,
            instructions=prompt,
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
                on_retry=lambda msg: print(f"[MarketStructureExpert] {msg}")
            )
        except Exception as e:
            print(f"[MarketStructureExpert] Validation failed after retries: {e}")
            final_result = {"data": "No data available"}

        ts = int(time.time() * 1000)
        if isinstance(final_result, dict):
            final_result["ts"] = ts
            final_result["meta"] = meta
        else:
            final_result = {"data": final_result, "ts": ts}

        output = _json_dumps_safe(final_result)
        print(output)
        return output


if __name__ == "__main__":
    expert = MarketStructureExpert()
    symbol = "ETHUSDT"
    full_context = asyncio.run(output.build_output("binance", symbol))
    query = build_agent_context("market_structure", full_context)
    asyncio.run(expert.run(query))
