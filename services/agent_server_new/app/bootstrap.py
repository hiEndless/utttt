from __future__ import annotations

import os

from services.agent_server_new.adapters.active_events_redis import RedisActiveEventsProvider
from services.agent_server_new.adapters.active_events_stub import StubActiveEventsProvider
from services.agent_server_new.adapters.execution_service_http import HttpExecutionDecisionProvider
from services.agent_server_new.adapters.market_state_http import HttpMarketStateProvider
from services.agent_server_new.adapters.position_context_stub import StubPositionContextProvider
from services.agent_server_new.adapters.symbol_memory_inmemory import InMemorySymbolMemoryAdapter
from services.agent_server_new.adapters.symbol_memory_redis import (
    RedisSymbolMemoryAdapter,
    RedisSymbolMemoryConfig,
    create_redis_client_from_env as create_memory_redis_client_from_env,
)
from services.agent_server_new.app.workflows.trade_event_workflow import TradeEventWorkflow


def _env_int(name: str, default: int, *, min_value: int | None = None) -> int:
    raw = str(os.getenv(name, str(default)) or str(default)).strip()
    try:
        out = int(raw)
    except Exception:
        out = int(default)
    if min_value is not None:
        out = max(int(min_value), out)
    return out


def create_trade_event_workflow_from_env() -> TradeEventWorkflow:
    """基于环境变量创建可运行的默认工作流。

    当前默认接线：
    - market_state: HttpMarketStateProvider.from_env()
    - position_context: StubPositionContextProvider()
    - active_events: 由 AGENT_ACTIVE_EVENTS_PROVIDER_MODE 控制（默认 stub）
    - execution_decider: 按环境变量 AGENT_EXECUTION_ENABLED 决定是否启用
    """
    active_events_provider_mode = str(os.getenv("AGENT_ACTIVE_EVENTS_PROVIDER_MODE", "stub") or "stub").strip().lower()
    active_events_provider = StubActiveEventsProvider()
    if active_events_provider_mode == "redis":
        try:
            active_events_provider = RedisActiveEventsProvider.from_env()
        except Exception:
            # 中文注释：provider 初始化失败时优雅降级，避免影响主决策链路可用性。
            active_events_provider = StubActiveEventsProvider()

    execution_enabled = str(os.getenv("AGENT_EXECUTION_ENABLED", "false") or "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    symbol_memory_enabled = str(os.getenv("AGENT_SYMBOL_MEMORY_ENABLED", "false") or "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
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
    ai_adaptive_enabled = str(os.getenv("AGENT_AI_ADAPTIVE_ENABLED", "false") or "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    ai_adaptive_mode = str(os.getenv("AGENT_AI_ADAPTIVE_MODE", "observe") or "observe").strip().lower()
    return TradeEventWorkflow(
        market_state=HttpMarketStateProvider.from_env(),
        position_context=StubPositionContextProvider(),
        active_events=active_events_provider,
        execution_decider=HttpExecutionDecisionProvider.from_env() if execution_enabled else None,
        recorder=None,
        symbol_memory_provider=symbol_memory_adapter,
        symbol_memory_recorder=symbol_memory_adapter,
        memory_recent_topk=memory_recent_topk,
        memory_recent_ttl_ms=memory_recent_ttl_ms,
        memory_dedup_key=memory_dedup_key,
        ai_adaptive_enabled=ai_adaptive_enabled,
        ai_adaptive_mode=ai_adaptive_mode,
    )
