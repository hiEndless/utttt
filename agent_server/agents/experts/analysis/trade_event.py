from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
from agent_server.configs.prompts.trade_event import get_prompt
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


class TradeEventExpert:
    name = "trade_event"

    # Define schema for LLM output validation
    SCHEMA = {
        "verdict": {
            "type": str,
            "required": True,
            "options": ["VALID", "WEAK_VALID", "INVALID"],
            "description": "裁决结果：VALID(有效) | WEAK_VALID(弱有效) | INVALID(无效)"
        },
        "alignment": {
            "type": str,
            "required": True,
            "options": ["ALIGNED", "CONFLICT", "STRONGLY_CONFLICT"],
            "description": "结构一致性：ALIGNED(一致) | CONFLICT(冲突) | STRONGLY_CONFLICT(严重冲突)"
        },
        "confidence_adjustment": {
            "type": str,
            "required": True,
            "options": ["none", "down"],
            "description": "可信度调整：none(无) | down(下调)"
        },
        "reasoning": {
            "type": list,
            "required": True,
            "description": "结构性原因列表（通常包含3点）"
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

        # 预处理 query，分离 LLM 核心输入与系统元数据
        try:
            qobj = json.loads(query) if isinstance(query, str) else (query or {})
        except Exception:
            qobj = {}

        # 构造 LLM 专用精简输入（去除 symbol, event_id 等元数据）
        trade_core = qobj.get("trade_core", {})
        context_data = qobj.get("context", {})
        
        # 展平结构: trade_core + context (包含 market_state, crowd_state 等)
        llm_input = {
            "trade_core": trade_core,
            **context_data
        }

        async def _run_llm():
            run_output = await agent.arun(
                Message(role="user", content=json.dumps(llm_input, ensure_ascii=False)),
                stream=False,
                debug_mode=False,
            )
            return run_output.content

        try:
            final_result = await validate_with_retry(
                llm_runner=_run_llm,
                validator=self.validator,
                max_retries=3,
                on_retry=lambda msg: print(f"[TradeEventExpert] {msg}")
            )
        except Exception as e:
            # Fallback to raw output or error if validation fails completely
            print(f"[TradeEventExpert] Validation failed after retries: {e}")
            final_result = {"error": str(e), "verdict": "INVALID", "alignment": "CONFLICT", "reasoning": ["Validation failed"]}

        # 构建产出物系统数据结构
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
    from agent_server.agents.experts.analysis.utils.trade_core_data import abstract_trade_event
    from agent_server.agent_context.builder import build_agent_context
    from agent_server.utils.redis_client import RedisClient
    from agent_server.agent_context.utils.crowd_interpreter import build_crowd_interpretation
    from agent_server.agent_context.utils.crowd_trend_analysis import enrich_and_clean_crowd_context

    final_signal = {'route': 'trade', 'exchange': 'binance', 'symbol': 'ETHUSDT', 'final_priority': 'low',
                    'event_id': 'binance.ETHUSDT.trade.open.1768803852754', 'event_type': 'trade.open',
                    'timestamp': '1768803852754', 'market_state': None, 'direction': None, 'confidence': None,
                    'confidence_numeric': None, 'priority_weight': None, 'l1_total_score': None, 'tf_hint': None,
                    'analysis_context': {}, 'meta': {'source_event_id': 'binance.ETHUSDT.trade.open.1768803852754',
                                                     'origin_source_hint': 'trade', 'is_short_term': False},
                    'trade_details': {'trade_id': 'e95cbad77cde4d8e80d405d1ff9a6f5f', 'position_side': 'SHORT',
                                      'current_size': '-0.007', 'entry_price': '3193.0', 'mark_price': '3193.00000000',
                                      'pnl_ratio': '0.0', 'action': 'OPEN', 'change_amount': '-0.007'}}

    exchange = final_signal.get("exchange")
    symbol = final_signal.get("symbol")
    event_id = final_signal.get("event_id")
    direction = final_signal.get("direction")
    trade_details = final_signal.get("trade_details")
    trade_core = abstract_trade_event(trade_details)

    expert = TradeEventExpert()

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
        
        # Inject deterministic crowd interpretation
        position_side = trade_details.get("position_side", "flat")
        interpretation = build_crowd_interpretation(full_context, position_side)
        ctx["crowd_interpretation"] = interpretation

        ctx["crowd_state"], ctx["crowd_trend_analysis"] = await enrich_and_clean_crowd_context(
            exchange, symbol, ctx.get("crowd_state", {})
        )
        
        query = {
            "symbol": symbol,
            "exchange": exchange,
            "event_id": event_id,
            "trade_core": trade_core,
            "context": ctx,
        }
        await expert.run(query)


    asyncio.run(_demo())
