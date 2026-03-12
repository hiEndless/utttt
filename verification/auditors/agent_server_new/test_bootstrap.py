import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.active_events_null import NullActiveEventsProvider
from services.agent_server_new.adapters.execution_service_http import HttpExecutionDecisionProvider
from services.agent_server_new.adapters.event_recorder_jsonl import JsonlEventRecorder
from services.agent_server_new.adapters.market_state_http import HttpMarketStateProvider
from services.agent_server_new.adapters.position_context_execution_http import HttpExecutionPositionContextProvider
from services.agent_server_new.adapters.symbol_memory_inmemory import InMemorySymbolMemoryAdapter
from services.agent_server_new.app.bootstrap import create_trade_event_workflow_from_env


def test_create_trade_event_workflow_from_env_wires_default_adapters(monkeypatch):
    monkeypatch.setenv("AGENT_MARKET_STATE_BASE_URL", "http://localhost:8300")
    monkeypatch.setenv("AGENT_MARKET_STATE_TIMEOUT_S", "9")
    monkeypatch.setenv("AGENT_ACTIVE_EVENTS_PROVIDER_MODE", "redis")
    monkeypatch.delenv("AGENT_EXECUTION_ENABLED", raising=False)

    import services.agent_server_new.app.bootstrap as mod

    monkeypatch.setattr(mod.RedisActiveEventsProvider, "from_env", lambda: NullActiveEventsProvider())
    wf = create_trade_event_workflow_from_env()
    assert isinstance(wf._market_state, HttpMarketStateProvider)  # noqa: SLF001
    assert isinstance(wf._position_context, HttpExecutionPositionContextProvider)  # noqa: SLF001
    assert isinstance(wf._active_events, NullActiveEventsProvider)  # noqa: SLF001
    assert wf._execution_decider is None  # noqa: SLF001
    assert wf._symbol_memory_provider is None  # noqa: SLF001
    assert wf._symbol_memory_recorder is None  # noqa: SLF001
    assert wf._ai_adaptive_enabled is False  # noqa: SLF001
    assert wf._ai_adaptive_mode == "observe"  # noqa: SLF001
    assert wf._market_state._base_url == "http://localhost:8300"  # noqa: SLF001
    assert float(wf._market_state._timeout_s) == 9.0  # noqa: SLF001


def test_create_trade_event_workflow_from_env_forbid_stub_position_context(monkeypatch):
    monkeypatch.setenv("AGENT_POSITION_CONTEXT_PROVIDER_MODE", "stub")
    try:
        create_trade_event_workflow_from_env()
        assert False, "expected RuntimeError when stub position context mode is used"
    except RuntimeError as exc:
        assert "unsupported AGENT_POSITION_CONTEXT_PROVIDER_MODE=stub" in str(exc)


def test_create_trade_event_workflow_from_env_enables_active_events_redis(monkeypatch):
    import services.agent_server_new.app.bootstrap as mod

    class _FakeRedisActiveEventsProvider:
        pass

    monkeypatch.setenv("AGENT_ACTIVE_EVENTS_PROVIDER_MODE", "redis")
    monkeypatch.setattr(mod.RedisActiveEventsProvider, "from_env", lambda: _FakeRedisActiveEventsProvider())
    wf = create_trade_event_workflow_from_env()
    assert wf._active_events.__class__.__name__ == "_FakeRedisActiveEventsProvider"  # noqa: SLF001


def test_create_trade_event_workflow_from_env_fallbacks_to_null_when_active_events_redis_failed(monkeypatch):
    import services.agent_server_new.app.bootstrap as mod

    monkeypatch.setenv("AGENT_ACTIVE_EVENTS_PROVIDER_MODE", "redis")
    monkeypatch.setenv("AGENT_ACTIVE_EVENTS_ALLOW_NULL_FALLBACK", "true")

    def _raise() -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(mod.RedisActiveEventsProvider, "from_env", _raise)
    wf = create_trade_event_workflow_from_env()
    assert isinstance(wf._active_events, NullActiveEventsProvider)  # noqa: SLF001


def test_create_trade_event_workflow_from_env_redis_failed_without_fallback_raises(monkeypatch):
    import services.agent_server_new.app.bootstrap as mod

    monkeypatch.setenv("AGENT_ACTIVE_EVENTS_PROVIDER_MODE", "redis")
    monkeypatch.setenv("AGENT_ACTIVE_EVENTS_ALLOW_NULL_FALLBACK", "false")

    def _raise() -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(mod.RedisActiveEventsProvider, "from_env", _raise)
    try:
        create_trade_event_workflow_from_env()
        assert False, "expected RuntimeError when redis provider init fails and null fallback is disabled"
    except RuntimeError as exc:
        assert "AGENT_ACTIVE_EVENTS_ALLOW_NULL_FALLBACK=true" in str(exc)


def test_create_trade_event_workflow_from_env_forbid_stub_active_events(monkeypatch):
    monkeypatch.setenv("AGENT_ACTIVE_EVENTS_PROVIDER_MODE", "stub")
    try:
        create_trade_event_workflow_from_env()
        assert False, "expected RuntimeError when stub active events mode is used"
    except RuntimeError as exc:
        assert "unsupported AGENT_ACTIVE_EVENTS_PROVIDER_MODE=stub" in str(exc)


def test_create_trade_event_workflow_from_env_prod_requires_redis_active_events(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME_PROFILE", "prod")
    monkeypatch.setenv("AGENT_ACTIVE_EVENTS_PROVIDER_MODE", "stub")
    try:
        create_trade_event_workflow_from_env()
        assert False, "expected RuntimeError when prod profile uses stub active events provider"
    except RuntimeError as exc:
        assert "AGENT_ACTIVE_EVENTS_PROVIDER_MODE=redis" in str(exc)


def test_create_trade_event_workflow_from_env_prod_forbid_redis_fallback(monkeypatch):
    import services.agent_server_new.app.bootstrap as mod

    monkeypatch.setenv("AGENT_RUNTIME_PROFILE", "prod")
    monkeypatch.setenv("AGENT_ACTIVE_EVENTS_PROVIDER_MODE", "redis")

    def _raise() -> object:
        raise RuntimeError("redis broken")

    monkeypatch.setattr(mod.RedisActiveEventsProvider, "from_env", _raise)
    try:
        create_trade_event_workflow_from_env()
        assert False, "expected RuntimeError when redis provider init fails in prod profile"
    except RuntimeError as exc:
        assert "failed to initialize redis active events provider in production" in str(exc)


def test_create_trade_event_workflow_from_env_enables_execution_decider(monkeypatch):
    monkeypatch.setenv("AGENT_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("AGENT_EXECUTION_BASE_URL", "http://localhost:9962")
    monkeypatch.setenv("AGENT_EXECUTION_TIMEOUT_S", "8")

    import services.agent_server_new.app.bootstrap as mod

    monkeypatch.setattr(mod.RedisActiveEventsProvider, "from_env", lambda: NullActiveEventsProvider())
    wf = create_trade_event_workflow_from_env()
    assert isinstance(wf._execution_decider, HttpExecutionDecisionProvider)  # noqa: SLF001


def test_create_trade_event_workflow_from_env_enables_jsonl_event_recorder(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_EVENT_RECORDER_MODE", "jsonl")
    monkeypatch.setenv("AGENT_EVENT_RECORDER_JSONL_PATH", str(tmp_path / "agent_events.jsonl"))

    import services.agent_server_new.app.bootstrap as mod

    monkeypatch.setattr(mod.RedisActiveEventsProvider, "from_env", lambda: NullActiveEventsProvider())
    wf = create_trade_event_workflow_from_env()
    assert isinstance(wf._recorder, JsonlEventRecorder)  # noqa: SLF001


def test_create_trade_event_workflow_from_env_invalid_event_recorder_mode(monkeypatch):
    monkeypatch.setenv("AGENT_EVENT_RECORDER_MODE", "stdout")
    try:
        create_trade_event_workflow_from_env()
        assert False, "expected RuntimeError when unsupported event recorder mode is used"
    except RuntimeError as exc:
        assert "unsupported AGENT_EVENT_RECORDER_MODE=stdout" in str(exc)


def test_create_trade_event_workflow_from_env_enables_symbol_memory_inmemory(monkeypatch):
    monkeypatch.setenv("AGENT_SYMBOL_MEMORY_ENABLED", "true")
    monkeypatch.delenv("AGENT_SYMBOL_MEMORY_BACKEND", raising=False)
    monkeypatch.setenv("AGENT_SYMBOL_MEMORY_CONTEXT_TOPK", "7")
    monkeypatch.setenv("AGENT_SYMBOL_MEMORY_CONTEXT_TTL_MS", "60000")
    monkeypatch.setenv("AGENT_SYMBOL_MEMORY_CONTEXT_DEDUP_KEY", "event_id")

    import services.agent_server_new.app.bootstrap as mod

    monkeypatch.setattr(mod.RedisActiveEventsProvider, "from_env", lambda: NullActiveEventsProvider())
    wf = create_trade_event_workflow_from_env()
    assert isinstance(wf._symbol_memory_provider, InMemorySymbolMemoryAdapter)  # noqa: SLF001
    assert isinstance(wf._symbol_memory_recorder, InMemorySymbolMemoryAdapter)  # noqa: SLF001
    assert wf._memory_recent_topk == 7  # noqa: SLF001
    assert wf._memory_recent_ttl_ms == 60000  # noqa: SLF001
    assert wf._memory_dedup_key == "event_id"  # noqa: SLF001


def test_create_trade_event_workflow_from_env_enables_symbol_memory_redis(monkeypatch):
    import services.agent_server_new.app.bootstrap as mod

    class _FakeRedis:
        pass

    monkeypatch.setenv("AGENT_SYMBOL_MEMORY_ENABLED", "true")
    monkeypatch.setenv("AGENT_SYMBOL_MEMORY_BACKEND", "redis")
    monkeypatch.setattr(mod, "create_memory_redis_client_from_env", lambda redis_url=None: _FakeRedis())  # noqa: ARG005
    monkeypatch.setattr(mod.RedisActiveEventsProvider, "from_env", lambda: NullActiveEventsProvider())

    wf = create_trade_event_workflow_from_env()
    assert wf._symbol_memory_provider.__class__.__name__ == "RedisSymbolMemoryAdapter"  # noqa: SLF001
    assert wf._symbol_memory_recorder.__class__.__name__ == "RedisSymbolMemoryAdapter"  # noqa: SLF001


def test_create_trade_event_workflow_from_env_enables_ai_adaptive_flags(monkeypatch):
    monkeypatch.setenv("AGENT_AI_ADAPTIVE_ENABLED", "true")
    monkeypatch.setenv("AGENT_AI_ADAPTIVE_MODE", "bounded_apply")

    import services.agent_server_new.app.bootstrap as mod

    monkeypatch.setattr(mod.RedisActiveEventsProvider, "from_env", lambda: NullActiveEventsProvider())
    wf = create_trade_event_workflow_from_env()
    assert wf._ai_adaptive_enabled is True  # noqa: SLF001
    assert wf._ai_adaptive_mode == "bounded_apply"  # noqa: SLF001
