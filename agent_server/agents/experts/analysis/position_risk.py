from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
from agent_server.configs.prompts.position_risk import get_prompt
from agno.models.message import Message
import json
import time
from agent_server.agents.utils import (
    _json_dumps_safe,
    LLMOutputValidator,
    validate_with_retry,
)
from agent_server.agent_context.output_store import save_agent_output
from agent_server.utils.account import get_available_exposure_pct
from agent_server.config import settings
from agent_server.risk.action_policy import enforce_position_risk_action


class PositionRiskExpert:
    name = "position_risk"

    # Define Schema
    SCHEMA = {
        "risk_state": {
            "type": str,
            "required": True,
            "options": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            "description": "Risk state level"
        },
        "recommended_action": {
            "type": str,
            "required": True,
            "options": ["ADD_POSITION", "HOLD", "DEFENSIVE", "REDUCE", "EXIT"],
            "description": "Recommended action"
        },
        "reduce_pct": {
            "type": float,
            "required": False,
            "range": (0.0, 1.0),
            "description": "Reduction percentage if action is REDUCE or EXIT"
        },
        "add_pct": {
            "type": float,
            "required": False,
            "range": (0.0, 1.0),
            "description": "Addition percentage if action is ADD_POSITION"
        },
        "tighten_stop": {
            "type": bool,
            "required": True,
            "description": "Whether to tighten stop loss"
        },
        "freeze_add_position_min": {
            "type": int,
            "required": True,
            "range": (0, 10000),
            "description": "Minutes to freeze adding position"
        },
        "reasoning": {
            "type": list,
            "required": True,
            "description": "List of reasons for the decision"
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
                on_retry=lambda msg: print(f"[PositionRiskExpert] {msg}")
            )
        except Exception as e:
            print(f"[PositionRiskExpert] Validation failed after retries: {e}")
            # Fallback for critical failure
            final_result = {
                "risk_state": "CRITICAL",
                "recommended_action": "HOLD",  # Safe default
                "reduce_pct": 0.0,
                "add_pct": 0.0,
                "tighten_stop": True,
                "freeze_add_position_min": 60,
                "reasoning": ["输出校验失败，已触发安全回退"]
            }

        # 构建产出物系统数据结构
        try:
            qobj = json.loads(query) if isinstance(query, str) else (query or {})
        except Exception:
            qobj = {}
        symbol = qobj.get("symbol") or "UNKNOWN"
        exchange = qobj.get("exchange") or "binance"
        event_id = qobj.get("event_id")
        trade_id = qobj.get("trade_id")
        ts = int(time.time() * 1000)

        # 动作策略层：确保 recommended_action 与硬规则 allowed_actions 语义一致（不一致则强制降级到可执行动作）
        try:
            risk_rules_decision = qobj.get("risk_rules_decision") or {}
            available_pct = (
                (qobj.get("operational_context") or {})
                .get("portfolio_context", {})
                .get("available_exposure_pct")
            )
            final_result, _ = enforce_position_risk_action(
                llm_output=final_result if isinstance(final_result, dict) else {},
                risk_rules_decision=risk_rules_decision,
                available_exposure_pct=available_pct,
            )
        except Exception:
            pass

        try:
            payload_obj = final_result if isinstance(final_result, dict) else json.loads(str(final_result))

            # 适配数据库字段映射
            if "recommended_action" in payload_obj:
                payload_obj["suggestion"] = payload_obj["recommended_action"]
            if "risk_state" in payload_obj:
                payload_obj["verdict"] = payload_obj["risk_state"]

        except Exception:
            payload_obj = {"raw": final_result}

        try:
            await save_agent_output(self.name, exchange, symbol, ts, payload_obj, event_id=event_id, trade_id=trade_id,
                                    model_id=model_id)
        except Exception as e:
            print(f"Failed to save agent output: {e}")

        output = _json_dumps_safe(final_result)
        print(output)
        return output


if __name__ == "__main__":
    from agent_server.reducers.temporal_state_reducer import reduce_temporal_state
    from agent_server.reducers.position_risk_decider import decide_position_action
    from agent_server.tools.get_position import get_position
    from agent_server.utils.redis_client import RedisClient
    from agent_server.agent_context.builder import build_agent_context
    from agent_server.agent_context.utils.crowd_interpreter import build_crowd_interpretation
    from agent_server.agent_context.utils.crowd_trend_analysis import enrich_and_clean_crowd_context
    import asyncio

    sv_out = {
        "_context_meta": {"agent": "signal_validation", "role": "technical_signal", "scope": ["short", "mid", "long"],
                          "uses_crowd_state": True, "exchange": "binance", "symbol": "BTCUSDT", "ts": 1730000000,
                          "event_id": "binance.BTCUSDT.trade.open.1768045518249"},
        "agent_output": {"verdict": "INVALID", "alignment": "STRONGLY_CONFLICT", "confidence_adjustment": "down",
                         "reasoning": ["所有关键周期（15m/30m/1h）tf_validation_conclusion均为conflict，构成硬性技术否决条件。",
                                       "市场短期虽为bearish，但动能持续减弱，且长期方向中性并具veto权，削弱方向环境支持。",
                                       "人群结构显示高拥挤度与高脆弱性，多头主导下易引发反向挤压，加剧方向失效风险。"]}}

    verdict = sv_out["agent_output"]["verdict"]
    alignment = sv_out["agent_output"].get("alignment")
    ts = sv_out["_context_meta"]["ts"]
    exchange = sv_out["_context_meta"]["exchange"]
    symbol = sv_out["_context_meta"]["symbol"]
    event_id = sv_out["_context_meta"]["event_id"]

    position = get_position(exchange, symbol)[0]
    position_side = position["position_side"]
    entry_ts = int(position["entry_ts"])
    trade_id = position.pop("trade_id")
    initialMargin = position.pop("initialMargin")  # 占用保证金，用于计算仓位占比


    async def _reduce(exchange: str, trade_id: str, symbol: str, position_side: str, verdict: str, alignment: str,
                      entry_ts: int,
                      ts: int):
        state = await reduce_temporal_state(
            exchange=exchange,
            trade_id=trade_id,
            symbol=symbol,
            position_side=position_side,
            verdict=verdict,
            alignment=alignment,
            entry_ts=entry_ts,
            event_ts=ts,
        )
        # print(json.dumps(state, ensure_ascii=False))
        return state


    state = asyncio.run(_reduce(exchange, trade_id, symbol, position_side, verdict, alignment, entry_ts, ts))

    expert = PositionRiskExpert()


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

        # 1. 使用 position_risk 视角构建上下文 (自动过滤无关字段)
        ctx = build_agent_context("position_risk", full_context)

        # Inject deterministic crowd interpretation
        # Note: position["position_side"] is already available here
        interpretation = build_crowd_interpretation(full_context, position_side)
        ctx["crowd_interpretation"] = interpretation

        # 2. 提取 Market Context (扁平化)
        ms = ctx.get("market_state", {})
        market_context = {
            "htf_trend": ms.get("long_term", {}).get("direction", "unknown"),
            "ltf_structure": ms.get("short_term", {}).get("structure", "unknown"),
            "vol_regime": ms.get("short_term", {}).get("risk", "unknown"),
            "distance_to_key_level_pct": ms.get("micro_term", {}).get("state", "unknown")
        }

        # 3. 提取 Crowd Context (扁平化)
        cs = ctx.get("crowd_state", {})
        crowd_context = {
            "crowding_level": cs.get("crowding_level", "unknown"),
            "funding_pressure": cs.get("funding_pressure", "unknown"),
            "fragility": cs.get("fragility", "unknown"),
            "bias": cs.get("bias", "unknown")
        }

        crowd_interpretation = ctx.get("crowd_interpretation", {})

        crowd_context, crowd_trend_analysis = await enrich_and_clean_crowd_context(exchange, symbol, crowd_context)

        # 4. 模拟 Operational Context (建议模式适配)
        # 从 Redis 获取上一次的建议记录，用于填充 action_state
        rc = RedisClient()
        last_suggestion_key = f"agent_output:{exchange}:{symbol}:position_risk:latest"
        last_suggestion_str = await rc.get(last_suggestion_key)

        # 获取账户余额计算可用仓位比例
        calculated_available_pct = await get_available_exposure_pct(exchange)

        # 默认初始化：应对首次运行或 Redis 无数据的情况
        # 使用 "HOLD" + 极长的时间间隔，表示“无近期操作历史”，让 Agent 从零开始评估
        last_action = "HOLD"
        last_action_ts = 0

        if last_suggestion_str:
            try:
                ls = json.loads(last_suggestion_str)
                # 兼容不同的存储结构，假设 payload 在最外层或 payload 字段
                meta = ls.get("_context_meta", ls)
                agent_output = ls.get("agent_output", ls)
                last_action = agent_output.get("recommended_action", "HOLD")
                last_action_ts = int(meta.get("ts", 0))
            except Exception:
                pass

        now_ms = int(time.time() * 1000)
        minutes_since_last = (now_ms - last_action_ts) / 1000 / 60 if last_action_ts > 0 else 9999

        # Load user specific config from DB here (TODO)
        user_config = {}
        risk_cfg = {**settings.risk_defaults, **user_config}

        operational_context = {
            "risk_limits": {
                "max_loss_pct": risk_cfg["max_loss_pct"],  # 最大亏损百分比 (建议参考值) 用户设置
                "max_holding_min": risk_cfg["max_holding_min"],  # 最长持仓时间 (0 表示不限制，由上游策略决定)
                "cooldown_after_invalid_min": risk_cfg["cooldown_after_invalid_min"]  # 建议模式下设为 0，保持对风险的实时敏感度
            },
            "portfolio_context": {
                "risk_mode": risk_cfg["risk_mode"],  # 账户风险模式: normal | conservative | aggressive
                "available_exposure_pct": calculated_available_pct,  # 剩余可用仓位
                "allow_add_position": risk_cfg["allow_add_position"]  # 是否允许加仓 (根据资金情况)
            },
            "action_state": {
                "last_action": last_action,  # 使用上一次的“建议”作为 last_action
                "last_action_min_ago": minutes_since_last,
                "recent_action_count": 0,  # 建议模式下可忽略频次限制
                "cooldown_active": False  # 建议模式下关闭冷却，允许随时输出最新建议
            },
            "system_mode": {
                "mode": risk_cfg["system_mode"],  # 标记为建议/顾问模式 系统整体模式: normal | defensive | recovery
                "allow_reverse": risk_cfg["allow_reverse"]  # 允许灵活调整观点
            }
        }

        # 5. 组装最终 Query
        decision_rules = decide_position_action(
            holding_duration_min=state["holding_duration_min"],
            time_since_last_event_min=int(state.get("time_since_last_event_min", 0) or 0),
            valid_streak=state["valid_streak"],
            invalid_streak=state["invalid_streak"],
            conflict_streak=state["conflict_streak"],
            risk_mode=risk_cfg["risk_mode"]  # 动态传入 risk_mode
        )

        query = {
            "symbol": symbol,
            "exchange": exchange,
            "event_id": event_id,
            "trade_id": trade_id,
            "ts_now": int(time.time() * 1000),
            "position_snapshot": position,
            "signal_verdict": sv_out["agent_output"],
            "temporal_state": state,
            "risk_rules_decision": decision_rules,
            "market_context": market_context,
            "crowd_context": crowd_context,
            "crowd_interpretation": crowd_interpretation,
            "crowd_trend_analysis": crowd_trend_analysis,
            "operational_context": operational_context  
        }

        # print("\n=== Agent Input Query ===")
        # print(json.dumps(query, indent=2, ensure_ascii=False))
        # print("=========================\n")

        await expert.run(query)


    asyncio.run(_demo())
