from __future__ import annotations

from agent_server_new.adapters.active_events_stub import StubActiveEventsProvider
from agent_server_new.adapters.market_state_http import HttpMarketStateProvider
from agent_server_new.adapters.position_context_stub import StubPositionContextProvider
from agent_server_new.app.workflows.trade_event_workflow import TradeEventWorkflow


def create_trade_event_workflow_from_env() -> TradeEventWorkflow:
    """基于环境变量创建可运行的默认工作流。

    当前默认接线：
    - market_state: HttpMarketStateProvider.from_env()
    - position_context: StubPositionContextProvider()
    - active_events: StubActiveEventsProvider()
    """
    return TradeEventWorkflow(
        market_state=HttpMarketStateProvider.from_env(),
        position_context=StubPositionContextProvider(),
        active_events=StubActiveEventsProvider(),
        recorder=None,
    )

