from agent_server.configs.prompts.trade_event import get_prompt
import json
import time
import asyncio
from typing import Any, Dict

from agent_server.agent_context.output_store import save_agent_output
from agent_server.agents.experts.base_llm_expert import BaseLLMExpert, QueryInput
from agent_server.agents.utils import _json_dumps_safe
from agent_server.configs.source import get_agent_config


class TradeEventExpert(BaseLLMExpert):
    name = "trade_event"
    version = "v1.0"

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

    def build_instructions(self, target_lang: str, **kwargs: Any) -> str:
        return get_prompt(target_lang)

    def build_llm_input(self, query_obj: Dict[str, Any], **kwargs: Any) -> Any:
        trade_core = query_obj.get("trade_core", {})
        position_effect = query_obj.get("position_effect", {})
        position_context = query_obj.get("position_context", {})
        context_data = query_obj.get("context", {})
        return {
            "trade_core": trade_core,
            "position_effect": position_effect,
            "position_context": position_context,
            **(context_data or {}),
        }

    def build_fallback_result(self, error: Exception, query_obj: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return {
            "error": str(error),
            "verdict": "INVALID",
            "alignment": "CONFLICT",
            "confidence_adjustment": "down",
            "reasoning": ["输出校验失败，已触发安全回退"],
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
        llm_query_obj["meta"] = dict(meta)
        # 将 positions 也传递给 LLM，便于结合仓位状态做解释与建议
        llm_query_obj["positions"] = positions
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
