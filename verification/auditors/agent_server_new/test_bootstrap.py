import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
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
    assert wf._ai_adaptive_enabled is False  # noqa: SLF001
    assert wf._ai_adaptive_mode == "observe"  # noqa: SLF001
    assert wf._market_state._base_url == "http://localhost:8300"  # noqa: SLF001
    assert float(wf._market_state._timeout_s) == 9.0  # noqa: SLF001


def test_create_trade_event_workflow_from_env_enables_active_events_redis(monkeypatch):
    import agent_server_new.app.bootstrap as mod

    class _FakeRedisActiveEventsProvider:
        pass

    monkeypatch.setenv("AGENT_ACTIVE_EVENTS_PROVIDER_MODE", "redis")
    monkeypatch.setattr(mod.RedisActiveEventsProvider, "from_env", lambda: _FakeRedisActiveEventsProvider())
    wf = create_trade_event_workflow_from_env()
    assert wf._active_events.__class__.__name__ == "_FakeRedisActiveEventsProvider"  # noqa: SLF001


def test_create_trade_event_workflow_from_env_fallbacks_to_stub_when_active_events_redis_failed(monkeypatch):
    import agent_server_new.app.bootstrap as mod

    monkeypatch.setenv("AGENT_ACTIVE_EVENTS_PROVIDER_MODE", "redis")

    def _raise() -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(mod.RedisActiveEventsProvider, "from_env", _raise)
    wf = create_trade_event_workflow_from_env()
    assert isinstance(wf._active_events, StubActiveEventsProvider)  # noqa: SLF001


def test_create_trade_event_workflow_from_env_enables_execution_decider(monkeypatch):
    monkeypatch.setenv("AGENT_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("AGENT_EXECUTION_BASE_URL", "http://localhost:9962")
    monkeypatch.setenv("AGENT_EXECUTION_TIMEOUT_S", "8")
    wf = create_trade_event_workflow_from_env()
    assert isinstance(wf._execution_decider, HttpExecutionDecisionProvider)  # noqa: SLF001


def test_create_trade_event_workflow_from_env_enables_symbol_memory_inmemory(monkeypatch):
    monkeypatch.setenv("AGENT_SYMBOL_MEMORY_ENABLED", "true")
    monkeypatch.delenv("AGENT_SYMBOL_MEMORY_BACKEND", raising=False)
    monkeypatch.setenv("AGENT_SYMBOL_MEMORY_CONTEXT_TOPK", "7")
    monkeypatch.setenv("AGENT_SYMBOL_MEMORY_CONTEXT_TTL_MS", "60000")
    monkeypatch.setenv("AGENT_SYMBOL_MEMORY_CONTEXT_DEDUP_KEY", "event_id")
    wf = create_trade_event_workflow_from_env()
    assert isinstance(wf._symbol_memory_provider, InMemorySymbolMemoryAdapter)  # noqa: SLF001
    assert isinstance(wf._symbol_memory_recorder, InMemorySymbolMemoryAdapter)  # noqa: SLF001
    assert wf._memory_recent_topk == 7  # noqa: SLF001
    assert wf._memory_recent_ttl_ms == 60000  # noqa: SLF001
    assert wf._memory_dedup_key == "event_id"  # noqa: SLF001


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


def test_create_trade_event_workflow_from_env_enables_ai_adaptive_flags(monkeypatch):
    monkeypatch.setenv("AGENT_AI_ADAPTIVE_ENABLED", "true")
    monkeypatch.setenv("AGENT_AI_ADAPTIVE_MODE", "bounded_apply")
    wf = create_trade_event_workflow_from_env()
    assert wf._ai_adaptive_enabled is True  # noqa: SLF001
    assert wf._ai_adaptive_mode == "bounded_apply"  # noqa: SLF001
