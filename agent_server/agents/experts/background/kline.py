from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
from agent_server.configs.prompts.kline import get_prompt
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


class KLineExpert:
    name = "kline"

    # Define Schema
    SCHEMA = {
        "interval": {
            "type": str,
            "required": True,
            "options": ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"],
            "description": "Time interval"
        },
        "symbol": {
            "type": str,
            "required": True,
            "description": "Trading symbol"
        },
        "trend": {
            "type": str,
            "required": True,
            "options": ["strong_bullish", "bullish", "neutral", "bearish", "strong_bearish"],
            "description": "Current trend direction"
        },
        "structure": {
            "type": dict,
            "required": True,
            "description": "Market structure details"
        },
        "environment": {
            "type": dict,
            "required": True,
            "description": "Market environment state"
        },
        "background_summary": {
            "type": str,
            "required": True,
            "description": "Brief summary of the market background"
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
                debug_mode=False,
            )
            return run_output.content

        try:
            final_result = await validate_with_retry(
                llm_runner=_run_llm,
                validator=self.validator,
                max_retries=3,
                on_retry=lambda msg: print(f"[KLineExpert] {msg}")
            )
        except Exception as e:
            print(f"[KLineExpert] Validation failed after retries: {e}")
            final_result = {
                "interval": query.get("interval", "unknown"),
                "symbol": symbol,
                "trend": "neutral",
                "structure": {"state": "consolidating", "key_level_proximity": "no_key_level"},
                "environment": {
                    "market_trend": "neutral",
                    "volatility_state": "medium",
                    "momentum_state": "neutral",
                    "risk_state": "medium"
                },
                "background_summary": f"Analysis failed: {str(e)}"
            }

        ts = int(time.time() * 1000)
        if isinstance(final_result, dict):
            final_result["ts"] = ts
        else:
            final_result = {"data": final_result, "ts": ts}

        interval = str(query.get("interval") or "unknown")
        key = f"background:{exchange}:{symbol}:{interval}"
        value_to_store = _ensure_json_serializable(final_result)
        client = RedisClient()
        await client.set_json(key, value_to_store)

        output = _json_dumps_safe(final_result)
        print(output)
        return output


if __name__ == "__main__":
    expert = KLineExpert()
    query = {"interval": "1m", "symbol": "BTCUSDT",
             "boll": {"upper_band": 90392.31434153463, "middle_band": 90069.12000000001,
                      "lower_band": 89745.92565846539, "bandwidth": 0.007176584861373524,
                      "percent_b": 0.7703945854529501},
             "ema": {"ema5": 90215.36588952654, "ema7": 90204.16950131317, "ema12": 90162.38820266027,
                     "ema20": 90102.87051100898, "ema26": 90072.19485459762, "ema50": 90053.77282589122,
                     "ema100": 90247.0264726327, "ema200": 90675.06520733665},
             "ma": {"ma5": 90227.92000000001, "ma10": 90213.48000000001, "ma20": 90069.12000000001, "ma50": 89923.828,
                    "ma200": 90833.16549999999},
             "rsi": {"rsi6": 59.75654739948335, "rsi12": 68.97606150620365, "rsi14": 63.27897266209745,
                     "rsi24": 61.77812287683215},
             "macd": {"dif": 90.19334805324615, "dea": 75.70591040067197, "macd": 28.974875305148373},
             "kdj": {"k": 61.56956203498415, "d": 69.52508038576617, "j": 45.6585253334201},
             "sr": {"R1": 92106.4, "R2": 92027.9, "R3": 91753.0, "S1": 89608.5, "S2": 89553.8, "S3": None},
             "vol": {"volatility": 0.0011337180897926615, "atr": 124.60695264332004, "dmi_plus": 25.145466323016883,
                     "dmi_minus": 19.007493477751076, "adx": 18.52322237652393}}
    asyncio.run(expert.run(query, "binance", query.get("symbol", "")))
