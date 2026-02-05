from typing import List, Dict, Any
from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
from agent_server.agent_context.market_structure import output
from agent_server.agent_context.builder import build_agent_context
from agent_server.configs.prompts.decision import prompt
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


class DecisionExpert:
    """
    决策层
    多专家 → 单决策 → 单风控
    所有专家 agent 的输出必须是“二级信号”，而不是原始信息
    作用：跨专家冲突消解 + 意图生成
    """
    version = "v1.0"
    name = "decision"

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
            "human_readable_only": True,
            "not_for_decision": True,
            "not_for_backtest": True
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
                on_retry=lambda msg: print(f"[DecisionExpert] {msg}")
            )
        except Exception as e:
            print(f"[DecisionExpert] failed after retries: {e}")
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
    from agent_server.utils.http_client import http_client
    from agent_server.config import settings

    API_KLINE_BACKGROUND = "/kline/background/read_multi"
    INDICATOR_INTERVALS = ["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]

    symbol = "RIVERUSDT"


    async def read_kline_backgrounds(exchange: str, symbol: str, intervals: List[str]) -> Dict[str, Any]:
        base = settings.api_base_url.rstrip("/")
        url = base + API_KLINE_BACKGROUND
        # 后端接口 /kline/indicators/read_multi 的请求体字段名为 intervals（多周期列表）
        payload = {"exchange": exchange, "symbol": symbol, "intervals": intervals}
        res: Any = None
        try:
            res = await http_client.request("POST", url, json=payload)
            data = (res or {}).get("data") if isinstance(res, dict) else None
        except Exception as e:
            # 统一返回错误信息，避免吞异常导致上层拿到 None/未定义变量
            data = {}
        return data


    async def _main() -> None:
        try:
            data = await read_kline_backgrounds("binance", symbol, INDICATOR_INTERVALS)
            kline_indicators = []
            if data:
                for k, v in data.items():
                    kline_indicators.append(v)

            expert = HumanMarketNarratorExpert()

            full_context = await output.build_output("binance", symbol)
            market_structure = build_agent_context("human_market_narrator", full_context)
            print(market_structure)

            query = {
                "symbol": market_structure["symbol"],
                "ts": market_structure["ts"],
                "market_structure": market_structure,
                "kline_indicators": kline_indicators,
            }
            await expert.run(query)
        finally:
            # 关闭 aiohttp 会话，避免 “Unclosed client session/connector” 警告
            await http_client.close()


    asyncio.run(_main())
