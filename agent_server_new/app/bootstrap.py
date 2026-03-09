from __future__ import annotations

import os

from agent_server_new.adapters.active_events_stub import StubActiveEventsProvider
from agent_server_new.adapters.execution_service_http import HttpExecutionDecisionProvider
from agent_server_new.adapters.market_state_http import HttpMarketStateProvider
from agent_server_new.adapters.position_context_stub import StubPositionContextProvider
from agent_server_new.adapters.symbol_memory_inmemory import InMemorySymbolMemoryAdapter
from agent_server_new.adapters.symbol_memory_redis import (
    RedisSymbolMemoryAdapter,
    RedisSymbolMemoryConfig,
    create_redis_client_from_env as create_memory_redis_client_from_env,
)
from agent_server_new.app.workflows.trade_event_workflow import TradeEventWorkflow


def create_trade_event_workflow_from_env() -> TradeEventWorkflow:
    """基于环境变量创建可运行的默认工作流。

    当前默认接线：
    - market_state: HttpMarketStateProvider.from_env()
    - position_context: StubPositionContextProvider()
    - active_events: StubActiveEventsProvider()
    - execution_decider: 按环境变量 AGENT_EXECUTION_ENABLED 决定是否启用
    """
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
                ttl_seconds=cfg.ttl_seconds,
                raw_topk=cfg.raw_topk,
            )
        else:
            symbol_memory_adapter = InMemorySymbolMemoryAdapter()
    return TradeEventWorkflow(
        market_state=HttpMarketStateProvider.from_env(),
        position_context=StubPositionContextProvider(),
        active_events=StubActiveEventsProvider(),
        execution_decider=HttpExecutionDecisionProvider.from_env() if execution_enabled else None,
        recorder=None,
        symbol_memory_provider=symbol_memory_adapter,
        symbol_memory_recorder=symbol_memory_adapter,
    )
