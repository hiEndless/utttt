from agent_server.configs.prompts.trade_behavior import get_prompt
import json
import time
import asyncio
from typing import Any, Dict
from agent_server.agent_context.market_structure import output
from agent_server.agent_context.output_store import save_agent_output
from agent_server.agents.experts.base_llm_expert import BaseLLMExpert, QueryInput
from agent_server.agents.utils import _json_dumps_safe
from agent_server.configs.source import get_agent_config


class TradeBehaviorExpert(BaseLLMExpert):
    """
    将所有审计型 Expert Agent 统一为这种“证据导向”的结构
    """
    name = "trade_behavior"
    version = "v1.2"  # Updated version for Layered Conflict Structure

    # Define schema for LLM output validation
    SCHEMA = {
        "dominant_cycle": {
            "type": str,
            "options": ["short_term", "mid_term", "long_term"],
            "description": "The cycle that currently dominates the structure"
        },
        "cycle_weights": {
            "type": dict,
            "schema": {
                "short_term": {"type": str, "options": ["high", "medium", "low", "veto_only"]},
                "mid_term": {"type": str, "options": ["high", "medium", "low", "veto_only"]},
                "long_term": {"type": str, "options": ["high", "medium", "low", "veto_only"]}
            }
        },
        "audit_breakdown": {
            "type": dict,
            "schema": {
                "directional_alignment": {
                    "type": dict,
                    "schema": {
                        "short_term": {"type": str, "options": ["ALIGNED", "CONFLICT", "NEUTRAL"]},
                        "mid_term": {"type": str, "options": ["ALIGNED", "CONFLICT", "NEUTRAL"]},
                        "long_term": {"type": str, "options": ["ALIGNED", "CONFLICT", "NEUTRAL"]}
                    }
                },
                "leverage_phase_match": {
                    "type": dict,
                    "schema": {
                        "short_term": {"type": str, "options": ["MATCH", "MISMATCH", "NEUTRAL", "NOT_APPLICABLE"]},
                        "mid_term": {"type": str, "options": ["MATCH", "MISMATCH", "NEUTRAL", "NOT_APPLICABLE"]},
                        "long_term": {"type": str, "options": ["MATCH", "MISMATCH", "NEUTRAL", "NOT_APPLICABLE"]}
                    }
                }
            }
        },
        "conflict_evidence": {
            "type": dict,
            "schema": {
                "directional_conflict": {
                    "type": list,
                    "description": "Evidence of directional conflicts"
                },
                "leverage_conflict": {
                    "type": list,
                    "description": "Evidence of leverage cycle mismatches"
                }
            }
        },
        "risk_exposure_flags": {
            "type": list,
            "description": "List of identified risk flags (e.g., crowding_risk, liquidity_vacuum)"
        },
        "audit_confidence": {
            "type": dict,
            "schema": {
                "level": {"type": str, "options": ["HIGH", "MEDIUM", "LOW"]},
                "structural_clarity": {
                    "type": str, 
                    "options": ["DOMINANT_CONFLICT", "CLEAR_DOMINANT_CYCLE", "MULTI_CYCLE_CONFLICT", "RISK_CLUSTER_PRESENT", "NOISE_DOMINATED", "VETO_TRIGGERED"]
                }
            }
        }
    }

    def build_instructions(self, target_lang: str, **kwargs: Any) -> str:
        return get_prompt(target_lang)

    def build_llm_input(self, query_obj: Dict[str, Any], **kwargs: Any) -> Any:
        trade_core = query_obj.get("trade", {})
        context_data = query_obj.get("structure_context", {})
        return {
            "trade": trade_core,
            "structure_context": context_data
        }

    def build_fallback_result(self, error: Exception, query_obj: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return {
            "dominant_cycle": "mid_term",
            "cycle_weights": {
                "short_term": "low",
                "mid_term": "low",
                "long_term": "low"
            },
            "audit_breakdown": {
                "directional_alignment": {
                    "short_term": "NEUTRAL",
                    "mid_term": "NEUTRAL",
                    "long_term": "NEUTRAL"
                },
                "leverage_phase_match": {
                    "short_term": "NEUTRAL",
                    "mid_term": "NEUTRAL",
                    "long_term": "NEUTRAL"
                }
            },
            "conflict_evidence": {
                "directional_conflict": ["System Error: Output validation failed"],
                "leverage_conflict": [str(error)]
            },
            "risk_exposure_flags": ["system_error_fallback"],
            "audit_confidence": {
                "level": "LOW",
                "structural_clarity": "NOISE_DOMINATED"
            }
        }

    async def run(self, query: QueryInput, **kwargs: Any) -> str:
        qobj = self._parse_query(query)
        meta = qobj.get("meta", {}) or {}
        positions = qobj.get("positions",  []) or []
        meta_user_id = str(meta.get("user_id") or meta.get("uid") or "").strip() or None

        cfg = get_agent_config(self.name, user_id=meta_user_id)
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
            meta_out = dict(meta)
            meta_out["ts"] = int(time.time() * 1000)
            meta_out["version"] = self.version
            meta_out["name"] = self.name
            return _json_dumps_safe({"error": "agent_config_missing", "missing": missing_keys, "meta": meta_out, "positions": positions})

        instructions = self.build_instructions(target_lang, **kwargs)
        agent = self._build_agent(model_id=model_id, base_url=base_url, api_key=api_key, instructions=instructions)
        # 将 meta 也传递给 LLM，但仍保持 qobj 作为业务字段集合，便于后续落库与默认值回退
        llm_query_obj = dict(qobj)
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
        meta["name"] = self.name

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
    from agent_server.tools.get_position import get_position
    from agent_server.agent_context.market_structure.holding_context_from_positions import (
        build_holding_context_from_positions,
    )
    from agent_server.agents.experts.analysis.utils.trade_core_data import abstract_trade_event
    from agent_server.agent_context.builder import build_agent_context

    final_signal = {'route': 'trade', 'exchange': 'binance', 'symbol': 'ETHUSDT', 'final_priority': 'low',
                    'event_id': 'binance.ETHUSDT.trade.increase.1768803852754', 'event_type': 'trade.open',
                    'timestamp': '1768803852754', 'market_state': None, 'direction': None, 'confidence': None,
                    'confidence_numeric': None, 'priority_weight': None, 'l1_total_score': None, 'tf_hint': None,
                    'analysis_context': {}, 'meta': {'source_event_id': 'binance.ETHUSDT.trade.open.1768803852754',
                                                     'origin_source_hint': 'trade', 'is_short_term': False},
                    'trade_details': {'trade_id': 'e95cbad77cde4d8e80d405d1ff9a6f5f', 'position_side': 'SHORT',
                                      'current_size': '-0.007', 'entry_price': '3193.0', 'mark_price': '3193.00000000',
                                      'pnl_ratio': '0.0', 'action': 'INCREASE', 'change_amount': '-0.007', 'initialMargin': 2.5, "exchange": "binance"}}

    exchange = final_signal.get("exchange")
    symbol = final_signal.get("symbol")
    event_id = final_signal.get("event_id")

    trade_details = final_signal.get("trade_details")
    trade_id = trade_details.get("trade_id")
    positions = get_position(exchange, symbol)
    if len(positions) == 2:
        # 如果是双开模式，根据 trade_id 找到对应的仓位记录
        matched_positions = [p for p in positions if str(p.get("trade_id")) == str(trade_id)]
        if matched_positions:
            positions = matched_positions

    holding_context = build_holding_context_from_positions(positions)
    holding_horizon = holding_context.get("horizon")
    # 给交易详情增加持仓周期
    trade_details["holding_horizon"] = holding_horizon
    
    # Calculate direction
    p_side = trade_details.get("position_side")
    p_action = trade_details.get("action")
    if p_side == "LONG":
        direction = "bullish" if p_action == "OPEN" else "bearish"
    else:  # SHORT
        direction = "bearish" if p_action == "OPEN" else "bullish"


    async def _get_trade_core():
        return await abstract_trade_event(trade_details)

    trade_core = asyncio.run(_get_trade_core())

    expert = TradeBehaviorExpert()

    async def _demo():
        full_context = await output.build_output("binance", symbol)
        ctx = build_agent_context("trade_behavior", full_context, horizon=holding_horizon)

        query = {
            "meta": {
                "symbol": symbol,
                "exchange": exchange,
                "event_id": event_id,
                "event_type": final_signal.get("route"),
                "direction": direction
            },
            "trade": trade_core,
            "structure_context": ctx,
            "positions": positions
        }
        # print(query)
        await expert.run(query)


    asyncio.run(_demo())
