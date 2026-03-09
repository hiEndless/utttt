import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent_server_new.adapters.active_events_stub import StubActiveEventsProvider
from agent_server_new.adapters.execution_service_http import HttpExecutionDecisionProvider
from agent_server_new.adapters.market_state_http import HttpMarketStateProvider
from agent_server_new.adapters.position_context_stub import StubPositionContextProvider
from agent_server_new.adapters.symbol_memory_inmemory import InMemorySymbolMemoryAdapter
from agent_server_new.app.bootstrap import create_trade_event_workflow_from_env


def test_create_trade_event_workflow_from_env_wires_default_adapters(monkeypatch):
    monkeypatch.setenv("AGENT_MARKET_STATE_BASE_URL", "http://localhost:8300")
    monkeypatch.setenv("AGENT_MARKET_STATE_TIMEOUT_S", "9")
    monkeypatch.delenv("AGENT_EXECUTION_ENABLED", raising=False)
    wf = create_trade_event_workflow_from_env()
    assert isinstance(wf._market_state, HttpMarketStateProvider)  # noqa: SLF001
    assert isinstance(wf._position_context, StubPositionContextProvider)  # noqa: SLF001
    assert isinstance(wf._active_events, StubActiveEventsProvider)  # noqa: SLF001
    assert wf._execution_decider is None  # noqa: SLF001
    assert wf._symbol_memory_provider is None  # noqa: SLF001
    assert wf._symbol_memory_recorder is None  # noqa: SLF001
    assert wf._market_state._base_url == "http://localhost:8300"  # noqa: SLF001
    assert float(wf._market_state._timeout_s) == 9.0  # noqa: SLF001


def test_create_trade_event_workflow_from_env_enables_execution_decider(monkeypatch):
    monkeypatch.setenv("AGENT_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("AGENT_EXECUTION_BASE_URL", "http://localhost:9962")
    monkeypatch.setenv("AGENT_EXECUTION_TIMEOUT_S", "8")
    wf = create_trade_event_workflow_from_env()
    assert isinstance(wf._execution_decider, HttpExecutionDecisionProvider)  # noqa: SLF001


def test_create_trade_event_workflow_from_env_enables_symbol_memory_inmemory(monkeypatch):
    monkeypatch.setenv("AGENT_SYMBOL_MEMORY_ENABLED", "true")
    monkeypatch.delenv("AGENT_SYMBOL_MEMORY_BACKEND", raising=False)
    wf = create_trade_event_workflow_from_env()
    assert isinstance(wf._symbol_memory_provider, InMemorySymbolMemoryAdapter)  # noqa: SLF001
    assert isinstance(wf._symbol_memory_recorder, InMemorySymbolMemoryAdapter)  # noqa: SLF001


def test_create_trade_event_workflow_from_env_enables_symbol_memory_redis(monkeypatch):
    import agent_server_new.app.bootstrap as mod

    class _FakeRedis:
        pass

    monkeypatch.setenv("AGENT_SYMBOL_MEMORY_ENABLED", "true")
    monkeypatch.setenv("AGENT_SYMBOL_MEMORY_BACKEND", "redis")
    monkeypatch.setattr(mod, "create_memory_redis_client_from_env", lambda redis_url=None: _FakeRedis())  # noqa: ARG005

    wf = create_trade_event_workflow_from_env()
    assert wf._symbol_memory_provider.__class__.__name__ == "RedisSymbolMemoryAdapter"  # noqa: SLF001
    assert wf._symbol_memory_recorder.__class__.__name__ == "RedisSymbolMemoryAdapter"  # noqa: SLF001
