from typing import List, Dict, Any
from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
from agent_server.agent_context.market_structure import output
from agent_server.agent_context.builder import build_agent_context
from agent_server.configs.prompts.decision import build_decision_prompt
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
        meta = query.pop("meta")
        cfg = get_agent_config(self.name)

        model_id = cfg.get("model_id", "deepseek-ai/DeepSeek-V3")
        base_url = cfg.get("llm_base_url")
        api_key = cfg.get("llm_api_key")

        model = OpenAILike(id=model_id, base_url=base_url, api_key=api_key)
        prompt = build_decision_prompt(query)

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
            final_result["meta"] = meta
            final_result["meta"]["ts"] = ts
            final_result["meta"]["version"] = self.version
        else:
            final_result = {"data": final_result, "ts": ts}

        output = _json_dumps_safe(final_result)
        print(output)
        return output


if __name__ == "__main__":
    from agent_server.utils.http_client import http_client
    from agent_server.config import settings
    from agent_server.agents.experts.orchestration.utils import (
        derive_directional_reference,
        derive_exposure_level,
        derive_holding_bias,
        derive_pnl_state,
    )

    signal = {"verdict": "ATTENUATE", "structural_alignment": "PARTIAL_CONFLICT", "risk_implication": "elevated",
              "reasoning": [
                  "signal_context.dominant_bucket = mid 且 mid_term.participant_positioning.structural_weight = high，表明中期为唯一主裁周期。",
                  "mid_term.participant_positioning.confidence.level = low，主裁周期未提供强方向性支持。",
                  "mid_term.structural_risks.crowding_risk = high，表明中期结构存在风险标记。",
                  "signal_direction = bullish 且 mid_term.participant_positioning.structural_weight = high，该方向未被主裁周期人群定位模式明确支持。",
                  "long_term.structural_weight = veto_only 且 long_term.confidence.level = low，未满足长期否决条件。"],
              "meta": {"symbol": "ETHUSDT", "exchange": "binance", "event_id": "ETHUSDT.final.1770290252305",
                       "event_type": "mixed", "ts": 1770304117868, "version": "v1.0"}, "positions": [
            {"symbol": "ETHUSDT", "position_side": "LONG", "size": "0.010", "notional": "21.73535821",
             "pnl_ratio": 0.004305523686720178, "open_time": 1770237903887,
             "trade_id": "9cedf3d0770041c8b11856c35ef664a2", "initialMargin": "2.17353583"}]}

    meta = signal.pop("meta")
    symbol = meta.get("symbol")
    positions = signal.pop("positions") or []

    async def _main() -> None:
        try:

            expert = DecisionExpert()

            full_context = await output.build_output("binance", symbol)
            market_structure = build_agent_context("decision", full_context)
            # 打印裁剪后的 market_structure（用于验证 forbidden_* 裁剪是否生效）
            # print(_json_dumps_safe(market_structure))

            directional_reference = derive_directional_reference(signal, market_structure)
            position_context = []
            for p in positions:
                if not isinstance(p, dict):
                    continue
                position_side = str(p.get("position_side") or "").upper()
                if position_side not in {"LONG", "SHORT"}:
                    continue
                position_context.append(
                    {
                        "position_side": position_side,
                        "exposure_level": derive_exposure_level(p),
                        "pnl_state": derive_pnl_state(p.get("pnl_ratio")),
                        "holding_bias": derive_holding_bias(position_side, directional_reference),
                    }
                )

            # print(signal)
            query = {
                "meta": meta,
                "market_structure": market_structure,
                "signal_verdict": signal,
                "position_state": position_context,
            }
            await expert.run(query)
        finally:
            # 关闭 aiohttp 会话，避免 “Unclosed client session/connector” 警告
            await http_client.close()


    asyncio.run(_main())
