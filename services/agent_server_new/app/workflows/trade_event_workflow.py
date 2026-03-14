from __future__ import annotations

import time
import logging
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from services.market_state_engine.src.contracts import MarketStateMSL

from services.agent_server_new.domain.contracts import ExecutionPlan, SignalDecision
from services.agent_server_new.domain.decision_plan_adapter import (
    build_decision_trace_payload,
    build_decision_plan_state,
    build_execution_decision_payload,
    build_recorder_stage_payloads,
    build_signal_decision_from_signal,
    build_symbol_memory_record_payload,
)
from services.agent_server_new.domain.msl_parser import _build_msl_from_dict
from services.agent_server_new.domain.signal_decision_agent import (
    RoutedHybridSignalDecisionAgent,
    RoutedRuleBasedSignalDecisionAgent,
    SignalDecisionAgent,
)
from services.agent_server_new.domain.signal_decision_context_policy import build_llm_observation_context
from services.agent_server_new.domain.signal_router import normalize_signal_event_type, route_signal_agent_key
from services.agent_server_new.experts.signal_evaluator import evaluate_signal
from services.agent_server_new.observability.decision_trace_schema_guard import validate_decision_trace_payload
from services.agent_server_new.ports.data.active_events_provider import ActiveEventsProvider
from services.agent_server_new.ports.data.position_context_provider import PositionContextProvider
from services.agent_server_new.ports.event_recorder import EventRecorder
from services.agent_server_new.ports.memory.symbol_memory_provider import SymbolMemoryProvider
from services.agent_server_new.ports.memory.symbol_memory_recorder import SymbolMemoryRecorder
from services.agent_server_new.ports.execution import ExecutionDecisionProvider
from services.agent_server_new.ports.llm_observer import LLMObserver
from services.agent_server_new.ports.market_state import MarketStateProvider
from services.agent_server_new.app.context_builder import ContextBuilder
from .event_context import EventContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TradeEventInput:
    """事件中心推送的最小输入集合（示例）。"""

    event_id: str
    exchange: str
    symbol: str
    signal_direction: str
    payload: Dict[str, Any]


@dataclass(frozen=True)
class WorkflowResult:
    """工作流输出：保留 agent 计划，并附带 execution 最终裁决（如可用）。"""

    agent_plan: ExecutionPlan
    signal_decision: SignalDecision
    execution_result: Optional[Dict[str, Any]] = None


def _extract_cross_horizon_policy(key_market_features: Dict[str, Any]) -> Dict[str, str]:
    feats = list((key_market_features or {}).get("features") or [])
    for item in feats:
        if str((item or {}).get("name") or "") != "cross_horizon":
            continue
        value = dict((item or {}).get("value") or {})
        return {
            "suggested_policy": str(value.get("suggested_policy") or "no_action"),
            "policy_reason": str(value.get("policy_reason") or "insufficient_evidence"),
        }
    return {"suggested_policy": "no_action", "policy_reason": "insufficient_evidence"}


def _sha256_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _signal_router_config_version(cfg: Dict[str, Any]) -> str:
    if not isinstance(cfg, dict):
        return ""
    try:
        stable = json.dumps(cfg, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        return ""
    return _sha256_text(stable)[:16]


def _signal_prompt_profiles_version(cfg: Dict[str, Any]) -> str:
    if not isinstance(cfg, dict):
        return ""
    try:
        stable = json.dumps(cfg, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        return ""
    return _sha256_text(stable)[:16]


def _sanitize_llm_contract_error_code(value: Any) -> str:
    code = str(value or "").strip()
    allowed = {
        "",
        "llm_raw_content_missing",
        "llm_json_parse_error",
        "llm_json_not_object",
        "llm_schema_validation_failed",
        "llm_confidence_parse_error",
    }
    return code if code in allowed else "llm_schema_validation_failed"


def _sanitize_llm_contract_errors(values: Any, *, limit: int = 8) -> list[str]:
    out: list[str] = []
    for item in list(values or []):
        text = str(item or "").strip()
        if not text:
            continue
        out.append(text)
        if len(out) >= max(1, int(limit)):
            break
    return out


class TradeEventWorkflow:
    """示例工作流：load context -> signal decision -> execution decider -> persist。"""

    def __init__(
        self,
        *,
        market_state: MarketStateProvider,
        position_context: PositionContextProvider,
        active_events: ActiveEventsProvider,
        execution_decider: Optional[ExecutionDecisionProvider] = None,
        recorder: Optional[EventRecorder] = None,
        symbol_memory_provider: SymbolMemoryProvider | None = None,
        symbol_memory_recorder: SymbolMemoryRecorder | None = None,
        llm_observer: LLMObserver | None = None,
        decision_trace_schema_validate: bool = True,
        memory_recent_topk: int = 5,
        memory_recent_ttl_ms: int = 24 * 60 * 60 * 1000,
        memory_dedup_key: str = "event_id",
        signal_router_config: Optional[Dict[str, Any]] = None,
        signal_decision_prompt_profiles: Optional[Dict[str, Dict[str, Any]]] = None,
        signal_decision_agent: SignalDecisionAgent | None = None,
        signal_router_config_source: str = "runtime",
        signal_router_config_version: str = "",
        signal_prompt_config_source: str = "runtime",
        signal_prompt_config_version: str = "",
    ) -> None:
        self._market_state = market_state
        self._position_context = position_context
        self._active_events = active_events
        self._execution_decider = execution_decider
        self._recorder = recorder
        self._symbol_memory_provider = symbol_memory_provider
        self._symbol_memory_recorder = symbol_memory_recorder
        self._llm_observer = llm_observer
        self._decision_trace_schema_validate = bool(decision_trace_schema_validate)
        self._memory_recent_topk = max(1, int(memory_recent_topk))
        self._memory_recent_ttl_ms = max(0, int(memory_recent_ttl_ms))
        self._memory_dedup_key = str(memory_dedup_key or "event_id").strip() or "event_id"
        self._signal_router_config = dict(signal_router_config or {})
        self._signal_decision_prompt_profiles = dict(signal_decision_prompt_profiles or {})
        self._signal_decision_agent = signal_decision_agent or (
            RoutedHybridSignalDecisionAgent(
                router_config=self._signal_router_config,
                signal_evaluator=evaluate_signal,
            )
            if self._llm_observer is not None
            else RoutedRuleBasedSignalDecisionAgent(
                router_config=self._signal_router_config,
                signal_evaluator=evaluate_signal,
            )
        )
        self._signal_router_config_source = str(signal_router_config_source or "runtime").strip() or "runtime"
        self._signal_router_config_version = str(signal_router_config_version or "").strip() or _signal_router_config_version(
            self._signal_router_config
        )
        self._signal_prompt_config_source = str(signal_prompt_config_source or "runtime").strip() or "runtime"
        self._signal_prompt_config_version = str(signal_prompt_config_version or "").strip() or _signal_prompt_profiles_version(
            self._signal_decision_prompt_profiles
        )

    async def run(self, event: TradeEventInput) -> ExecutionPlan:
        result = await self.run_with_result(event)
        return result.agent_plan

    async def run_with_result(self, event: TradeEventInput) -> WorkflowResult:
        builder = ContextBuilder(
            market_state=self._market_state,
            position_context=self._position_context,
            active_events=self._active_events,
            symbol_memory_provider=self._symbol_memory_provider,
            max_key_features=10,
            memory_recent_topk=self._memory_recent_topk,
            memory_recent_ttl_ms=self._memory_recent_ttl_ms,
            memory_dedup_key=self._memory_dedup_key,
        )
        built = await builder.build(
            event_id=event.event_id,
            exchange=event.exchange,
            symbol=event.symbol,
            signal_payload=event.payload,
        )
        ctx = built.ctx

        if self._recorder:
            await self._recorder.record_market_context(
                event.event_id,
                {
                    "ts": int(time.time() * 1000),
                    "symbol": ctx.symbol,
                    "msl": ctx.msl.to_llm_dict(),
                    "key_market_features": dict(ctx.key_market_features),
                    "active_events": list(ctx.active_events),
                    "position_context": dict(ctx.position_context),
                },
            )

        llm_observation = {
            "status": "disabled",
            "provider": "",
            "model": "",
            "raw_content_hash": "",
        }
        llm_result_raw: Optional[Dict[str, Any]] = None
        routed_agent_key = route_signal_agent_key(
            signal_event=dict(ctx.signal_event or {}),
            router_config=self._signal_router_config,
        )
        if self._llm_observer is not None:
            llm_ctx = build_llm_observation_context(
                decision_agent_key=routed_agent_key,
                key_market_features=dict(ctx.key_market_features or {}),
                active_events=list(ctx.active_events or []),
                prompt_profiles=self._signal_decision_prompt_profiles,
                features_limit=8,
                events_limit=8,
            )
            llm_payload = {
                "event_id": event.event_id,
                "exchange": event.exchange,
                "symbol": event.symbol,
                "signal_direction": event.signal_direction,
                "decision_agent_key": llm_ctx["decision_agent_key"],
                "decision_prompt": dict(llm_ctx.get("decision_prompt") or {}),
                "signal_event": dict(ctx.signal_event or {}),
                "msl": ctx.msl.to_llm_dict(),
                "key_market_features": dict(llm_ctx.get("key_market_features") or {}),
                "active_events": list(llm_ctx.get("active_events") or []),
            }
            try:
                llm_result = await self._llm_observer.observe(llm_payload)
                llm_result_raw = dict(llm_result or {})
                llm_observation = {
                    "status": str((llm_result or {}).get("status") or "ok"),
                    "provider": str((llm_result or {}).get("provider") or ""),
                    "model": str((llm_result or {}).get("model") or ""),
                    "raw_content_hash": _sha256_text((llm_result or {}).get("raw_content")),
                }
                if self._recorder:
                    await self._recorder.record_agent_output(
                        event.event_id,
                        "llm_observer",
                        dict(llm_result or {}),
                    )
            except Exception as exc:
                logger.warning("llm observer failed, fallback to rule engine event_id=%s err=%s", event.event_id, exc)
                llm_observation = {
                    "status": "error",
                    "provider": "",
                    "model": "",
                    "raw_content_hash": "",
                    "fallback": "rule_engine",
                    "error_type": exc.__class__.__name__,
                }
                llm_result_raw = {"status": "error", "error_type": exc.__class__.__name__}
                if self._recorder:
                    await self._recorder.record_agent_output(
                        event.event_id,
                        "llm_observer",
                        {"status": "error", "fallback": "rule_engine", "error": str(exc)},
                    )
        eval_result = self._signal_decision_agent.decide(
            decision_agent_key=routed_agent_key,
            signal_direction=event.signal_direction,
            msl=ctx.msl,
            key_market_features=dict(ctx.key_market_features),
            active_events=list(ctx.active_events),
            signal_event=dict(ctx.signal_event),
            position_context=dict(ctx.position_context),
            llm_result=llm_result_raw,
        )
        signal = eval_result.signal
        event_type_diag = normalize_signal_event_type(
            signal_event=dict(ctx.signal_event or {}),
            router_config=self._signal_router_config,
        )
        signal_decision = build_signal_decision_from_signal(
            decision_id=event.event_id,
            exchange=event.exchange,
            symbol=event.symbol,
            signal=signal,
            llm_observation=llm_observation,
            decision_agent_key=eval_result.decision_agent_key,
            decision_mode=eval_result.decision_mode,
            llm_parse_status=eval_result.llm_parse_status,
        )

        if self._recorder:
            await self._recorder.record_agent_output(
                event.event_id,
                "signal_evaluator",
                {
                    "pipeline_mode": "minimal",
                    "decision_agent_key": eval_result.decision_agent_key,
                    "decision_mode": eval_result.decision_mode,
                    "llm_parse_status": eval_result.llm_parse_status,
                    "llm_contract_error_code": _sanitize_llm_contract_error_code(eval_result.llm_contract_error_code),
                    "llm_contract_errors": _sanitize_llm_contract_errors(eval_result.llm_contract_errors),
                    "direction": signal.direction,
                    "verdict": signal.verdict,
                    "confidence": {"level": signal.confidence.level, "score": signal.confidence.score},
                    "invalidation_reasons": list(signal.invalidation_reasons),
                    "notes": signal.notes,
                },
            )

        ch = _extract_cross_horizon_policy(dict(ctx.key_market_features or {}))
        position_ctx = dict(ctx.position_context or {})
        compat = build_decision_plan_state(
            signal=signal,
            msl=ctx.msl,
            position_context=position_ctx,
            active_events=list(ctx.active_events),
            signal_event=dict(ctx.signal_event or {}),
            cross_horizon=ch,
        )
        plan = compat.plan

        execution_result: Optional[Dict[str, Any]] = None
        if self._execution_decider is not None:
            decision_payload = build_execution_decision_payload(
                default_decision_id=event.event_id,
                default_exchange=event.exchange,
                default_symbol=event.symbol,
                signal_decision=signal_decision,
                plan=plan,
                cross_horizon=ch,
                prompt_config_source=self._signal_prompt_config_source,
                prompt_config_version=self._signal_prompt_config_version,
            )
            if self._recorder:
                await self._recorder.record_agent_output(
                    event.event_id,
                    "execution_decider_request",
                    dict(decision_payload),
                )
            direction_intent = str(decision_payload.get("direction_intent") or "").strip().lower()
            if direction_intent not in {"long", "short", "neutral"}:
                logger.warning(
                    "执行层裁决前阻断非法 direction_intent event_id=%s direction_intent=%s",
                    event.event_id,
                    direction_intent,
                )
                if self._recorder:
                    await self._recorder.record_agent_output(
                        event.event_id,
                        "execution_decider",
                        {
                            "status": "blocked",
                            "error_type": "InvalidDirectionIntent",
                            "error": f"direction_intent must be long/short/neutral, got: {direction_intent}",
                            "direction_intent": direction_intent,
                        },
                    )
            else:
                try:
                    execution_result = await self._execution_decider.decide(decision_payload)
                    logger.info(
                        "执行层裁决完成 event_id=%s action=%s reason=%s",
                        event.event_id,
                        str(execution_result.get("execution_action") or "unknown"),
                        str(execution_result.get("reject_reason") or ""),
                    )
                    if self._recorder:
                        await self._recorder.record_agent_output(
                            event.event_id,
                            "execution_decider",
                            execution_result,
                        )
                except Exception as exc:  # pragma: no cover
                    logger.warning("执行层裁决失败 event_id=%s err=%s", event.event_id, exc)
                    if self._recorder:
                        await self._recorder.record_agent_output(
                            event.event_id,
                            "execution_decider",
                            {
                                "status": "error",
                                "error_type": exc.__class__.__name__,
                                "error": str(exc),
                            },
                        )

        if self._recorder:
            trace_payload = build_decision_trace_payload(
                event_id=ctx.event_id,
                exchange=ctx.exchange,
                symbol=ctx.symbol,
                ts=ctx.timestamp_ms,
                signal_event=dict(ctx.signal_event),
                msl=ctx.msl.to_llm_dict(),
                key_market_features=dict(ctx.key_market_features),
                signal=signal,
                signal_decision=signal_decision,
                pipeline_mode="minimal",
                llm_contract_error_code=_sanitize_llm_contract_error_code(eval_result.llm_contract_error_code),
                llm_contract_errors=_sanitize_llm_contract_errors(eval_result.llm_contract_errors),
                router_config_source=self._signal_router_config_source,
                router_config_version=self._signal_router_config_version,
                prompt_config_source=self._signal_prompt_config_source,
                prompt_config_version=self._signal_prompt_config_version,
                event_type_diag=event_type_diag,
                state=compat,
                llm_observation=dict(llm_observation),
            )
            stage_payloads = build_recorder_stage_payloads(
                state=compat,
                signal_decision=signal_decision,
                pipeline_mode="minimal",
                cross_horizon=ch,
                decision_trace_payload=trace_payload,
            )
            if self._decision_trace_schema_validate:
                valid, errors = validate_decision_trace_payload(stage_payloads.get("decision_trace") or {})
                if not valid:
                    logger.warning(
                        "decision_trace schema validation failed event_id=%s error_count=%s",
                        event.event_id,
                        len(errors),
                    )
                    await self._recorder.record_agent_output(
                        event.event_id,
                        "decision_trace_schema_guard",
                        {
                            "status": "invalid",
                            "error_count": len(errors),
                            "errors": list(errors[:10]),
                        },
                    )
            for stage_name, stage_payload in stage_payloads.items():
                await self._recorder.record_agent_output(event.event_id, stage_name, stage_payload)

        if self._symbol_memory_recorder is not None:
            contract_warnings = [str(x) for x in list((ctx.key_market_features or {}).get("contract_warnings") or []) if x]
            await self._symbol_memory_recorder.record_symbol_memory(
                event.exchange,
                event.symbol,
                build_symbol_memory_record_payload(
                    ts=int(time.time() * 1000),
                    event_id=event.event_id,
                    signal_event=dict(ctx.signal_event or {}),
                    msl_summary=str(ctx.msl.summary or ""),
                    signal=signal,
                    state=compat,
                    cross_horizon=ch,
                    contract_warnings=contract_warnings,
                    execution_result=dict(execution_result or {}),
                ),
            )

        return WorkflowResult(agent_plan=plan, signal_decision=signal_decision, execution_result=execution_result)


def _msl_from_dict(d: Dict[str, Any]) -> MarketStateMSL:
    """兼容旧测试入口，统一委托给 adapter 层单点 MSL 解析器。"""
    return _build_msl_from_dict(dict(d or {}))
