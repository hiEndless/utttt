from typing import List, Dict, Any
from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
from agent_server.agent_context.market_structure import output
from agent_server.agent_context.builder import build_agent_context
from agent_server.configs.prompts.human_market_narrator import get_prompt
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


class HumanMarketNarratorExpert:
    """
    叙事层
    生成人类可读的市场解读、复盘报告、直观说明
    不用做后续的回测，仅供前端展示

    | 特性       | Market Structure Agent        | Human Market Narrator Agent                |
    | -------- | ------------------------------ | ------------------------------------------ |
    | **目标**   | 冻结系统在当前时间的结构认知      | 生成人类可读的市场解读、复盘报告、直观说明                      |
    | **输入数据** | 已计算好的周期桶结构数据        | 可使用周期桶结构数据，也可用额外的 K 线指标、趋势、动能、波动性等更直观的市场信息 |
    | **输出**   | narrative（去方向性、去预测性）  | 自然语言解读、口语化描述，可附加方向性印象、情绪感知、市场状态总结          |
    | **方向性**  | 不允许（去 bullish/bearish）   | 可以适度呈现，但基于人类可读表达，非系统决策逻辑                   |
    | **可回测性** | 高，可做结构化统计             | 低，主要用于展示/复盘/报告                             |

    """
    version = "v1.0"
    name = "human_market_narrator"

    # Define Schema
    SCHEMA = {
        # 人类可读的市场叙事正文
        "market_story": {
            "type": "string",
            "required": True,
            "description": "用于阅读展示的人类可读市场叙事正文",
        },
        # 阅读辅助层：表达读完叙事后的主观方向印象（非信号、非结论）
        "reading_bias_overlay": {
            "type": "object",
            "required": True,
            "description": "阅读辅助层（short_term/mid_term/long_term 的方向与置信度）",
            "schema": {
                "short_term": {
                    "type": "object",
                    "required": True,
                    "schema": {
                        "direction": {
                            "type": "string",
                            "required": True,
                            "options": [
                                "bullish",
                                "neutral_to_bullish",
                                "neutral",
                                "neutral_to_bearish",
                                "bearish",
                            ],
                        },
                        "confidence": {
                            "type": "string",
                            "required": True,
                            "options": ["low", "medium", "high"],
                        },
                    },
                },
                "mid_term": {
                    "type": "object",
                    "required": True,
                    "schema": {
                        "direction": {
                            "type": "string",
                            "required": True,
                            "options": [
                                "bullish",
                                "neutral_to_bullish",
                                "neutral",
                                "neutral_to_bearish",
                                "bearish",
                            ],
                        },
                        "confidence": {
                            "type": "string",
                            "required": True,
                            "options": ["low", "medium", "high"],
                        },
                    },
                },
                "long_term": {
                    "type": "object",
                    "required": True,
                    "schema": {
                        "direction": {
                            "type": "string",
                            "required": True,
                            "options": [
                                "bullish",
                                "neutral_to_bullish",
                                "neutral",
                                "neutral_to_bearish",
                                "bearish",
                            ],
                        },
                        "confidence": {
                            "type": "string",
                            "required": True,
                            "options": ["low", "medium", "high"],
                        },
                    },
                },
            },
        },
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
        target_lang = cfg.get("language", "zh")

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
                on_retry=lambda msg: print(f"[HumanMarketNarratorExpert] {msg}")
            )
        except Exception as e:
            print(f"[HumanMarketNarratorExpert] Validation failed after retries: {e}")
            final_result = {"data": "No data available"}

        ts = int(time.time() * 1000)
        if isinstance(final_result, dict):
            final_result["ts"] = ts
            final_result["meta"] = meta
        else:
            final_result = {"data": final_result, "ts": ts}

        output = _json_dumps_safe(final_result)
        
        # Save to Redis if exchange is available
        exchange = query.get("exchange")
        symbol = query.get("symbol")
        if exchange and symbol:
            try:
                key = f"background:{exchange}:{symbol}:market_structure"
                redis_client = RedisClient()
                await redis_client.set_json(key, final_result)
                print(f"[HumanMarketNarratorExpert] Saved to Redis: {key}")
            except Exception as e:
                print(f"[HumanMarketNarratorExpert] Failed to save to Redis: {e}")
        
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
