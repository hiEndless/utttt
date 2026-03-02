from typing import List, Dict, Any, Optional, Set
from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
from agent_server.agent_context.market_structure import output
from agent_server.agent_context.builder import build_agent_context
from agent_server.configs.prompts.decision import build_decision_prompt
from agno.models.message import Message
import json
from agent_server.agent_context.output_store import save_agent_output
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
        "trade_intent_range": {
            "type": "object",
            "required": True,
            "schema": {
                "allowed_actions": {"type": "array", "required": True},
                "forbidden_actions": {"type": "array", "required": True},
                "risk_bias": {
                    "type": "string",
                    "required": True,
                    "options": ["defensive", "conservative", "neutral"],
                },
            },
        },
        "reasoning": {"type": "array", "required": True},
    }

    def __init__(self):
        self.validator = LLMOutputValidator(self.SCHEMA)

    async def _get_llm_result(self, query_payload: Dict[str, Any], *, user_id: Optional[str], target_lang: str) -> Any:
        query_payload.pop("meta", {})

        cfg = get_agent_config(self.name, user_id=user_id)
        model_id = cfg.get("model_id", "deepseek-ai/DeepSeek-V3")
        base_url = cfg.get("llm_base_url")
        api_key = cfg.get("llm_api_key")

        model = OpenAILike(id=model_id, base_url=base_url, api_key=api_key)
        prompt = build_decision_prompt(query_payload, target_lang=target_lang)

        agent = Agent(
            model=model,
            instructions=prompt,
        )

        async def _run_llm():
            run_output = await agent.arun(
                Message(role="user", content=json.dumps(query_payload, ensure_ascii=False)),
                stream=False,
                debug_mode=True,
            )
            return run_output.content

        return await validate_with_retry(
            llm_runner=_run_llm,
            validator=self.validator,
            max_retries=3,
            on_retry=lambda msg: print(f"[DecisionExpert] {msg}"),
        )

    @staticmethod
    def _extract_position_sides(position_state: Any) -> Set[str]:
        sides: Set[str] = set()
        for item in list(position_state or []):
            if not isinstance(item, dict):
                continue
            side = str(item.get("position_side") or "").upper()
            if side in {"LONG", "SHORT"}:
                sides.add(side)
        return sides

    @staticmethod
    def _filter_position_state(position_state: Any, position_side: str) -> List[Dict[str, Any]]:
        side = str(position_side or "").upper()
        out: List[Dict[str, Any]] = []
        for item in list(position_state or []):
            if not isinstance(item, dict):
                continue
            if str(item.get("position_side") or "").upper() != side:
                continue
            out.append(item)
        return out

    @staticmethod
    def _extract_trade_id(query: Dict[str, Any], position_side: Optional[str] = None) -> Optional[str]:
        side = str(position_side or "").upper()

        # 优先从原始 positions 中提取 trade_id（最贴近真实持仓来源）
        positions = query.get("positions") or []
        for p in list(positions or []):
            if not isinstance(p, dict):
                continue
            if side and str(p.get("position_side") or "").upper() != side:
                continue
            trade_id = p.get("trade_id") or p.get("tradeId")
            if trade_id:
                return str(trade_id)

        # 兜底：从 position_state 中提取（若上游在 position_state 中透传了 trade_id）
        position_state = query.get("position_state") or []
        for p in list(position_state or []):
            if not isinstance(p, dict):
                continue
            if side and str(p.get("position_side") or "").upper() != side:
                continue
            trade_id = p.get("trade_id") or p.get("tradeId")
            if trade_id:
                return str(trade_id)

        # 最后兜底：若 meta 里已带 trade_id，直接复用
        meta = query.get("meta") or {}
        if isinstance(meta, dict) and meta.get("trade_id"):
            return str(meta.get("trade_id"))
        return None

    async def run(self, query: dict) -> str:
        # 确保 query 是字典
        query = query or {}

        # 1. 构建 LLM 请求用的 query_local (需要移除 meta 和 positions)
        query_local = dict(query)
        meta = query_local.pop("meta", {}) or {}
        meta_user_id = str(meta.get("user_id") or meta.get("uid") or "").strip() or None

        cfg = get_agent_config(self.name, user_id=meta_user_id)
        model_id = cfg.get("model_id", "deepseek-ai/DeepSeek-V3")
        target_lang = cfg.get("language", "zh")

        # 不将原始 positions 透传给 LLM（仅用于本地提取 trade_id）
        query_local.pop("positions", None)

        position_state = query_local.get("position_state")
        position_sides = self._extract_position_sides(position_state)

        ts = int(time.time() * 1000)
        base_meta = dict(meta)
        base_meta["ts"] = ts
        base_meta["version"] = self.version
        base_meta["name"] = self.name

        # 多空双开：按仓位方向拆分并发请求 LLM，再将两份结果合并为一个列表
        if position_sides == {"LONG", "SHORT"}:
            async def _run_one(side: str) -> Dict[str, Any]:
                payload = dict(query_local)
                payload["position_state"] = self._filter_position_state(position_state, side)
                try:
                    result = await self._get_llm_result(payload, user_id=meta_user_id, target_lang=target_lang)
                except Exception as e:
                    print(f"[DecisionExpert] failed after retries ({side}): {e}")
                    result = {"data": "No data available"}

                # 统一构建 meta
                result_meta = dict(base_meta)
                result_meta["position_side"] = side
                trade_id = self._extract_trade_id(query, side)
                if trade_id:
                    result_meta["trade_id"] = trade_id

                if isinstance(result, dict):
                    result["meta"] = result_meta
                    return result
                return {"data": result, "meta": result_meta}

            results = await asyncio.gather(_run_one("LONG"), _run_one("SHORT"))
            final_result = {"meta": base_meta, "results": results}
            output_text = _json_dumps_safe(final_result)
            print(output_text)
            return output_text

        try:
            final_result = await self._get_llm_result(query_local, user_id=meta_user_id, target_lang=target_lang)
        except Exception as e:
            print(f"[DecisionExpert] failed after retries: {e}")
            final_result = {"data": "No data available"}

        if isinstance(final_result, dict):
            final_result["meta"] = base_meta
        else:
            final_result = {"data": final_result, "meta": base_meta}

        trade_id = self._extract_trade_id(query)
        if trade_id and isinstance(final_result.get("meta"), dict):
            final_result["meta"]["trade_id"] = trade_id

        try:
            await save_agent_output(
                self.name,
                base_meta.get("exchange", "binance"),
                base_meta.get("symbol", "UNKNOWN"),
                base_meta.get("ts"),
                final_result,
                event_id=base_meta.get("event_id"),
                trade_id=trade_id or base_meta.get("trade_id"),
                model_id=model_id,
            )
        except Exception as e:
            print(f"[DecisionExpert] Save failed: {e}")

        output_text = _json_dumps_safe(final_result)
        print(output_text)
        return output_text


if __name__ == "__main__":
    from agent_server.utils.http_client import http_client
    from agent_server.config import settings
    from agent_server.agents.experts.orchestration.utils import (
        transform_positions_to_decision_context,
    )
    from agent_server.agent_context.market_structure.holding_context_from_positions import (
        build_holding_context_from_positions,
    )

    signal = {
        "dominant_cycle": "mid_term",
        "cycle_weights": {
            "short_term": "low",
            "mid_term": "high",
            "long_term": "veto_only"
        },
        "audit_breakdown": {
            "directional_alignment": {
                "short_term": "NEUTRAL",
                "mid_term": "CONFLICT",
                "long_term": "CONFLICT"
            },
            "leverage_phase_match": {
                "short_term": "NOT_APPLICABLE",
                "mid_term": "NOT_APPLICABLE",
                "long_term": "NOT_APPLICABLE"
            }
        },
        "conflict_evidence": {
            "directional_conflict": ["Mid-term structure shows clear resistance", "Long-term trend is bearish"],
            "leverage_conflict": []
        },
        "risk_exposure_flags": ["crowding_risk"],
        "audit_confidence": {
            "level": "MEDIUM",
            "structural_clarity": "DOMINANT_CONFLICT"
        },
        "meta": {
            "symbol": "ETHUSDT",
            "exchange": "binance",
            "event_id": "ETHUSDT.final.1770290252305",
            "event_type": "mixed",
            "ts": 1770304117868,
            "version": "v1.0",
            "direction": "bullish"
        },
        "positions": [
            {
                "symbol": "ETHUSDT",
                "position_side": "LONG",
                "size": "0.010",
                "notional": "21.73535821",
                "pnl_ratio": 0.004305523686720178,
                "open_time": 1770237903887,
                "trade_id": "9cedf3d0770041c8b11856c35ef664a2",
                "initialMargin": "2.17353583"
            }
        ]
    }

    meta = signal.pop("meta")
    symbol = meta.get("symbol")
    positions = signal.pop("positions") or []

    holding_context = build_holding_context_from_positions(positions)
    holding_horizon = holding_context.get("horizon")

    async def _main() -> None:
        try:

            expert = DecisionExpert()

            full_context = await output.build_output("binance", symbol)
            market_structure = build_agent_context("decision", full_context, horizon=holding_horizon)
            # 打印裁剪后的 market_structure（用于验证 forbidden_* 裁剪是否生效）
            # print(_json_dumps_safe(market_structure))

            # positions -> position_state（决策层可直接消费的派生持仓状态）
            position_context = transform_positions_to_decision_context(
                positions,
                signal=signal,
                market_structure=market_structure,
            )

            # print(signal)
            query = {
                "meta": meta,
                "market_structure": market_structure,
                "signal_verdict": signal,
                "position_state": position_context,
                "positions": positions,
            }
            await expert.run(query)
        finally:
            # 关闭 aiohttp 会话，避免 “Unclosed client session/connector” 警告
            await http_client.close()


    asyncio.run(_main())
