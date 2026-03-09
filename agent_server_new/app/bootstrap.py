from __future__ import annotations

import os

from agent_server_new.adapters.active_events_stub import StubActiveEventsProvider
from agent_server_new.adapters.execution_service_http import HttpExecutionDecisionProvider
from agent_server_new.adapters.market_state_http import HttpMarketStateProvider
from agent_server_new.adapters.position_context_stub import StubPositionContextProvider
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
    return TradeEventWorkflow(
        market_state=HttpMarketStateProvider.from_env(),
        position_context=StubPositionContextProvider(),
        active_events=StubActiveEventsProvider(),
        execution_decider=HttpExecutionDecisionProvider.from_env() if execution_enabled else None,
        recorder=None,
    )
