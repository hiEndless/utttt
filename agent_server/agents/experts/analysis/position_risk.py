from agent_server.configs.prompts.position_risk import get_prompt
import json
import time
from typing import Any, Dict

from agent_server.agents.experts.base_llm_expert import BaseLLMExpert, QueryInput
from agent_server.utils.account import account_state
from agent_server.agent_context.market_structure import output
from agent_server.configs.source import get_agent_config
from agent_server.agent_context.output_store import save_agent_output
from agent_server.agents.utils import (
    _ensure_json_serializable,
    _json_dumps_safe,
    LLMOutputValidator,
    validate_with_retry,
)


class PositionRiskExpert(BaseLLMExpert):
    name = "position_risk"
    version = "v1.0"

    # 中文注释：LLM 输出严格 schema（与 prompts/position_risk.py 的“输出要求”一致）
    SCHEMA = {
        "risk_action": {
            "type": "string",
            "options": ["hold", "reduce", "scale_in_small", "exit"],
            "required": True,
            "description": "风控动作：hold/reduce/scale_in_small/exit",
        },
        "exposure_delta": {
            "type": "object",
            "required": True,
            "description": "相对当前仓位的变化比例（percentage）",
            "schema": {
                "type": {
                    "type": "string",
                    "options": ["percentage"],
                    "required": True,
                },
                "value": {
                    "type": "number",
                    "required": True,
                    "range": (-1.0, 1.0),
                },
            },
        },
        "reasoning": {
            "type": "array",
            "required": True,
            "description": "2-5条事实+结构/约束驱动理由（中文）",
        },
    }

    def build_instructions(self, target_lang: str, **kwargs: Any) -> str:
        return get_prompt(target_lang)

    def build_fallback_result(self, error: Exception, query_obj: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        # 中文注释：校验失败时返回保守“持有”，并补齐 execution_state 所需字段
        return {
            "risk_action": "hold",
            "exposure_delta": {"type": "percentage", "value": 0.0},
            "reasoning": ["输出校验失败，已触发安全回退", str(error)],
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
        position = qobj.pop("position", []) or []

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
        payload_obj["position"] = position

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
        result_for_return["position"] = position
        output = _json_dumps_safe(result_for_return)
        print(output)
        return output


if __name__ == "__main__":
    from agent_server.tools.get_position import get_position
    from agent_server.agent_context.builder import build_agent_context
    from agent_server.agent_context.market_structure.holding_context import build_holding_context
    from agent_server.agents.experts.analysis.utils.execution_constraint_aggregator import ExecutionConstraintAggregator
    import asyncio
    from agent_server.risk.execution_state_aggregator import aggregate_execution_state_and_store

    sv_out = {'verdict': 'ATTENUATE', 'structural_alignment': 'PARTIAL_CONFLICT', 'risk_implication': 'elevated'}

    d_out = {'trade_intent_range': {'allowed_actions': ['hold', 'reduce', 'scale_in_small'],
                                    'forbidden_actions': ['aggressive_add', 'reverse_position'],
                                    'risk_bias': 'conservative'},
             'meta': {'symbol': 'ETHUSDT', 'exchange': 'binance', 'event_id': 'ETHUSDT.final.1770290252305',
                      'ts': 1770675469101, 'version': 'v1.0', 'trade_id': '9cedf3d0770041c8b11856c35ef664a2'}}

    execution_constraint = ExecutionConstraintAggregator().aggregate(sv_out, d_out).get("execution_constraint")
    meta = d_out.get("meta")
    trade_id = meta.get("trade_id")
    exchange = meta.get("exchange")
    symbol = meta.get("symbol")

    positions = get_position(exchange, symbol)
    position = {}
    for p in positions:
        if p["trade_id"] == trade_id:
            horizon = build_holding_context(p["open_time"], int(time.time() * 1000)).get("horizon")
            position = {
                "position_side": p["position_side"],
                "size": p["size"],
                "notional": p["notional"],
                "pnl_ratio": p["pnl_ratio"],
                "holding_duration": horizon.split("_")[0],
            }
            initialMargin = float(p.pop("initialMargin", 0))  # 占用保证金，用于计算仓位占比
            leverage = str(p.pop("leverage", ""))  # 杠杆倍数，用于计算仓位占比
            break
    # print(position)

    expert = PositionRiskExpert()


    async def _demo():
        full_context = await output.build_output("binance", symbol)
        market_structure = build_agent_context("position_risk", full_context)
        # 打印裁剪后的 market_structure（用于验证 forbidden_* 裁剪是否生效）
        # print(_json_dumps_safe(market_structure))

        # 从 Redis 获取上一次的建议记录，用于填充 action_state
        # rc = RedisClient()
        # last_suggestion_key = f"agent_output:{exchange}:{symbol}:position_risk:latest"
        # last_suggestion_str = await rc.get(last_suggestion_key)

        # 获取账户余额计算可用仓位比例
        account_risk_state = await account_state(exchange)
        account_risk_state["position_occupancy_ratio"] = initialMargin / (account_risk_state.get("balance", 1) * float(leverage))

        query = {
            "meta": meta,
            "market_structure": market_structure,
            "position": position,
            "account_risk_state": account_risk_state,
            "execution_constraint": execution_constraint,
        }
        # print( query)

        # print("\n=== Agent Input Query ===")
        # print(json.dumps(query, indent=2, ensure_ascii=False))
        # print("=========================\n")

        # 中文注释：等待 LLM 输出完成后再返回
        raw = await expert.run(query)
        return json.loads(raw)


    # out_put = asyncio.run(_demo())

    async def _execution():
        out_put = await _demo()
        # 生成仓位风控状态
        execution_state = await aggregate_execution_state_and_store(
            risk_action_output=out_put,
            signal_validation_output=sv_out,
            previous_execution_state=None,
            now_ts=int(time.time() * 1000),
            exchange=exchange,
            trade_id=trade_id,
            symbol=symbol,
        )
        print(json.dumps(execution_state, ensure_ascii=False))


    asyncio.run(_execution())
