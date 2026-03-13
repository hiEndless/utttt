from __future__ import annotations

import hashlib
import json
import logging
import os

from services.agent_server_new.adapters.active_events_redis import RedisActiveEventsProvider
from services.agent_server_new.adapters.active_events_null import NullActiveEventsProvider
from services.agent_server_new.adapters.execution_service_http import HttpExecutionDecisionProvider
from services.agent_server_new.adapters.event_recorder_jsonl import JsonlEventRecorder
from services.agent_server_new.adapters.llm_openai_compatible import OpenAICompatibleLLMObserver
from services.agent_server_new.adapters.market_state_http import HttpMarketStateProvider
from services.agent_server_new.adapters.position_context_execution_http import HttpExecutionPositionContextProvider
from services.agent_server_new.adapters.symbol_memory_inmemory import InMemorySymbolMemoryAdapter
from services.agent_server_new.adapters.symbol_memory_redis import (
    RedisSymbolMemoryAdapter,
    RedisSymbolMemoryConfig,
    create_redis_client_from_env as create_memory_redis_client_from_env,
)
from services.agent_server_new.domain.signal_router import (
    load_signal_router_config_from_env,
    validate_signal_router_config,
)
from services.agent_server_new.domain.signal_decision_prompt_profiles import (
    load_signal_decision_prompt_profiles_from_env,
    validate_signal_decision_prompt_profiles,
)
from services.agent_server_new.app.workflows.trade_event_workflow import TradeEventWorkflow
from services.agent_server_new.runtime.llm_runtime import load_llm_runtime_from_env

logger = logging.getLogger(__name__)
_ALLOWED_SIGNAL_AGENT_KEYS = {"technical", "liquidation", "onchain", "social_news", "generic"}


def _env_int(name: str, default: int, *, min_value: int | None = None) -> int:
    raw = str(os.getenv(name, str(default)) or str(default)).strip()
    try:
        out = int(raw)
    except Exception:
        out = int(default)
    if min_value is not None:
        out = max(int(min_value), out)
    return out


def _env_bool(name: str, default: str = "false") -> bool:
    return str(os.getenv(name, default) or default).strip().lower() in {"1", "true", "yes", "on"}


def _signal_router_config_version(cfg: dict) -> str:
    try:
        stable = json.dumps(cfg, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        return ""
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]


def _signal_prompt_config_version(cfg: dict) -> str:
    try:
        stable = json.dumps(cfg, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        return ""
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]


def create_trade_event_workflow_from_env() -> TradeEventWorkflow:
    """基于环境变量创建可运行的默认工作流。

    当前默认接线：
    - market_state: HttpMarketStateProvider.from_env()
    - position_context: 由 AGENT_POSITION_CONTEXT_PROVIDER_MODE 控制（默认 http）
    - active_events: 由 AGENT_ACTIVE_EVENTS_PROVIDER_MODE 控制（默认 redis）
      - Redis 初始化失败默认抛错；仅当 AGENT_ACTIVE_EVENTS_ALLOW_NULL_FALLBACK=true 且非生产环境才回退 null provider
    - execution_decider: 按环境变量 AGENT_EXECUTION_ENABLED 决定是否启用
    """
    runtime_profile = str(os.getenv("AGENT_RUNTIME_PROFILE", "dev") or "dev").strip().lower()
    active_events_provider_mode = str(os.getenv("AGENT_ACTIVE_EVENTS_PROVIDER_MODE", "redis") or "redis").strip().lower()
    allow_null_fallback = _env_bool("AGENT_ACTIVE_EVENTS_ALLOW_NULL_FALLBACK", "false")
    if runtime_profile in {"prod", "production"} and active_events_provider_mode != "redis":
        raise RuntimeError("production profile requires AGENT_ACTIVE_EVENTS_PROVIDER_MODE=redis")

    active_events_provider = NullActiveEventsProvider()
    if active_events_provider_mode == "redis":
        try:
            active_events_provider = RedisActiveEventsProvider.from_env()
        except Exception as exc:
            if runtime_profile in {"prod", "production"}:
                raise RuntimeError("failed to initialize redis active events provider in production") from exc
            if allow_null_fallback:
                # 中文注释：仅在显式允许时，非生产环境才降级为 null provider，避免静默丢失事件背景。
                logger.warning("active_events redis provider init failed, fallback to null provider: %s", exc)
                active_events_provider = NullActiveEventsProvider()
            else:
                raise RuntimeError(
                    "failed to initialize redis active events provider; "
                    "set AGENT_ACTIVE_EVENTS_ALLOW_NULL_FALLBACK=true to allow null fallback in non-production"
                ) from exc
    else:
        raise RuntimeError(f"unsupported AGENT_ACTIVE_EVENTS_PROVIDER_MODE={active_events_provider_mode}")

    position_context_provider_mode = str(
        os.getenv("AGENT_POSITION_CONTEXT_PROVIDER_MODE", "http") or "http"
    ).strip().lower()
    if position_context_provider_mode != "http":
        raise RuntimeError(f"unsupported AGENT_POSITION_CONTEXT_PROVIDER_MODE={position_context_provider_mode}")
    position_context_provider = HttpExecutionPositionContextProvider.from_env(runtime_profile=runtime_profile)
    llm_runtime = load_llm_runtime_from_env(runtime_profile=runtime_profile)
    llm_observer = None
    if llm_runtime.enabled and llm_runtime.ready:
        if llm_runtime.provider == "openai_compatible":
            llm_observer = OpenAICompatibleLLMObserver.from_env(config=llm_runtime)
        else:
            logger.warning("unsupported AGENT_LLM_PROVIDER=%s; llm observer disabled", llm_runtime.provider)
    if llm_runtime.enabled and not llm_runtime.ready:
        logger.warning(
            "llm runtime enabled but config incomplete; decision pipeline still uses rule-based flow "
            "(missing AGENT_LLM_MODEL_ID/API_KEY)"
        )

    execution_enabled = _env_bool("AGENT_EXECUTION_ENABLED", "false")
    event_recorder_mode = str(os.getenv("AGENT_EVENT_RECORDER_MODE", "none") or "none").strip().lower()
    recorder = None
    if event_recorder_mode == "jsonl":
        recorder = JsonlEventRecorder.from_env()
    elif event_recorder_mode not in {"none", ""}:
        raise RuntimeError(f"unsupported AGENT_EVENT_RECORDER_MODE={event_recorder_mode}")
    symbol_memory_enabled = _env_bool("AGENT_SYMBOL_MEMORY_ENABLED", "false")
    symbol_memory_backend = str(os.getenv("AGENT_SYMBOL_MEMORY_BACKEND", "inmemory") or "inmemory").strip().lower()
    symbol_memory_adapter = None
    if symbol_memory_enabled:
        if symbol_memory_backend == "redis":
            cfg = RedisSymbolMemoryConfig.from_env()
            redis_client = create_memory_redis_client_from_env(cfg.redis_url)
            symbol_memory_adapter = RedisSymbolMemoryAdapter(
                redis_client=redis_client,
                raw_key_template=cfg.raw_key_template,
                summary_key_template=cfg.summary_key_template,
                symbol_index_key=cfg.symbol_index_key,
                ttl_seconds=cfg.ttl_seconds,
                raw_topk=cfg.raw_topk,
            )
        else:
            symbol_memory_adapter = InMemorySymbolMemoryAdapter()
    memory_recent_topk = _env_int("AGENT_SYMBOL_MEMORY_CONTEXT_TOPK", 5, min_value=1)
    memory_recent_ttl_ms = _env_int("AGENT_SYMBOL_MEMORY_CONTEXT_TTL_MS", 86_400_000, min_value=0)
    memory_dedup_key = str(os.getenv("AGENT_SYMBOL_MEMORY_CONTEXT_DEDUP_KEY", "event_id") or "event_id").strip() or "event_id"
    decision_trace_schema_validate = _env_bool("AGENT_DECISION_TRACE_SCHEMA_VALIDATE", "true")
    ai_adaptive_enabled = _env_bool("AGENT_AI_ADAPTIVE_ENABLED", "false")
    ai_adaptive_mode = str(os.getenv("AGENT_AI_ADAPTIVE_MODE", "observe") or "observe").strip().lower()
    legacy_pipeline_enabled = _env_bool("AGENT_LEGACY_PIPELINE_ENABLED", "true")
    if (not legacy_pipeline_enabled) and (not execution_enabled):
        msg = "minimal pipeline requires AGENT_EXECUTION_ENABLED=true to keep decision->execution closed loop"
        if runtime_profile in {"prod", "production"}:
            raise RuntimeError(msg)
        logger.warning("%s (non-production)", msg)
    signal_router_config_file = str(os.getenv("AGENT_SIGNAL_ROUTER_CONFIG_FILE", "") or "").strip()
    signal_router_config = load_signal_router_config_from_env()
    try:
        validate_signal_router_config(signal_router_config, allowed_agent_keys=_ALLOWED_SIGNAL_AGENT_KEYS)
    except ValueError as exc:
        if runtime_profile in {"prod", "production"}:
            raise RuntimeError(f"invalid signal router config in production: {exc}") from exc
        raise RuntimeError(f"invalid signal router config: {exc}") from exc
    signal_prompt_profiles = load_signal_decision_prompt_profiles_from_env()
    signal_prompt_config_file = str(os.getenv("AGENT_SIGNAL_DECISION_PROMPT_CONFIG_FILE", "") or "").strip()
    try:
        validate_signal_decision_prompt_profiles(signal_prompt_profiles, allowed_agent_keys=_ALLOWED_SIGNAL_AGENT_KEYS)
    except ValueError as exc:
        if runtime_profile in {"prod", "production"}:
            raise RuntimeError(f"invalid signal decision prompt config in production: {exc}") from exc
        raise RuntimeError(f"invalid signal decision prompt config: {exc}") from exc
    return TradeEventWorkflow(
        market_state=HttpMarketStateProvider.from_env(),
        position_context=position_context_provider,
        active_events=active_events_provider,
        execution_decider=HttpExecutionDecisionProvider.from_env() if execution_enabled else None,
        recorder=recorder,
        llm_observer=llm_observer,
        symbol_memory_provider=symbol_memory_adapter,
        symbol_memory_recorder=symbol_memory_adapter,
        decision_trace_schema_validate=decision_trace_schema_validate,
        memory_recent_topk=memory_recent_topk,
        memory_recent_ttl_ms=memory_recent_ttl_ms,
        memory_dedup_key=memory_dedup_key,
        ai_adaptive_enabled=ai_adaptive_enabled,
        ai_adaptive_mode=ai_adaptive_mode,
        legacy_pipeline_enabled=legacy_pipeline_enabled,
        signal_router_config=signal_router_config,
        signal_decision_prompt_profiles=signal_prompt_profiles,
        signal_router_config_source=(
            f"env:{signal_router_config_file}"
            if signal_router_config_file
            else "default:services/agent_server_new/config/signal_router_profiles.json"
        ),
        signal_router_config_version=_signal_router_config_version(signal_router_config),
        signal_prompt_config_source=(
            f"env:{signal_prompt_config_file}"
            if signal_prompt_config_file
            else "default:services/agent_server_new/config/signal_decision_prompt_profiles.json"
        ),
        signal_prompt_config_version=_signal_prompt_config_version(signal_prompt_profiles),
    )
