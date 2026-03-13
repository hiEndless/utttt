import asyncio
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.llm_openai_compatible import OpenAICompatibleLLMObserver
from services.agent_server_new.runtime.llm_runtime import LLMRuntimeConfig


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = int(status_code)
        self._payload = dict(payload)
        self.request = httpx.Request("POST", "http://unit.test/chat/completions")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"status={self.status_code}",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )

    def json(self) -> dict:
        return dict(self._payload)


class _FakeAsyncClient:
    def __init__(self, scripted: list[object], counter: dict):
        self._scripted = scripted
        self._counter = counter

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        _ = (exc_type, exc, tb)
        return None

    async def post(self, url: str, json, headers):  # noqa: ANN001
        _ = (url, headers)
        self._counter["calls"] += 1
        self._counter["last_json"] = dict(json or {})
        event = self._scripted.pop(0)
        if isinstance(event, Exception):
            raise event
        return event


def test_openai_compatible_llm_observer_success(monkeypatch):
    import services.agent_server_new.adapters.llm_openai_compatible as mod

    counter = {"calls": 0}
    scripted = [
        _FakeResponse(
            200,
            {
                "choices": [{"message": {"content": "{\"trend\":\"up\"}"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )
    ]
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda timeout: _FakeAsyncClient(scripted, counter))
    obs = OpenAICompatibleLLMObserver(model_id="gpt-4o-mini", api_key="sk-test", base_url="http://unit.test", retry_max=0)
    out = asyncio.run(obs.observe({"symbol": "ETHUSDT"}))
    assert out["status"] == "ok"
    assert out["provider"] == "openai_compatible"
    assert out["model"] == "gpt-4o-mini"
    assert out["raw_content"] == "{\"trend\":\"up\"}"
    assert counter["calls"] == 1


def test_openai_compatible_llm_observer_uses_decision_prompt(monkeypatch):
    import services.agent_server_new.adapters.llm_openai_compatible as mod

    counter = {"calls": 0}
    scripted = [
        _FakeResponse(
            200,
            {
                "choices": [{"message": {"content": "{\"trend\":\"up\"}"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )
    ]
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda timeout: _FakeAsyncClient(scripted, counter))
    obs = OpenAICompatibleLLMObserver(model_id="gpt-4o-mini", api_key="sk-test", base_url="http://unit.test", retry_max=0)
    asyncio.run(
        obs.observe(
            {
                "symbol": "ETHUSDT",
                "decision_prompt": {
                    "focus": "onchain_flow_validation",
                    "checklist": ["wallet_flow_direction"],
                    "avoid": ["execution_action"],
                },
            }
        )
    )
    messages = list(counter.get("last_json", {}).get("messages") or [])
    system = dict(messages[0] or {}) if messages else {}
    text = str(system.get("content") or "")
    assert "focus=onchain_flow_validation" in text
    assert "checklist=wallet_flow_direction" in text


def test_openai_compatible_llm_observer_retries_then_success(monkeypatch):
    import services.agent_server_new.adapters.llm_openai_compatible as mod

    counter = {"calls": 0}
    scripted = [
        httpx.TimeoutException("timeout"),
        _FakeResponse(200, {"choices": [{"message": {"content": "{}"}}], "usage": {}}),
    ]
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda timeout: _FakeAsyncClient(scripted, counter))
    obs = OpenAICompatibleLLMObserver(model_id="gpt-4o-mini", api_key="sk-test", base_url="http://unit.test", retry_max=1, retry_backoff_s=0.0)
    out = asyncio.run(obs.observe({"symbol": "ETHUSDT"}))
    assert out["status"] == "ok"
    assert counter["calls"] == 2


def test_openai_compatible_llm_observer_from_env(monkeypatch):
    cfg = LLMRuntimeConfig(
        enabled=True,
        provider="openai_compatible",
        model_id="gpt-4o-mini",
        base_url="http://unit.test/v1",
        api_key="sk-test",
        api_key_env_name="",
        ready=True,
    )
    monkeypatch.setenv("AGENT_LLM_TIMEOUT_S", "7")
    monkeypatch.setenv("AGENT_LLM_RETRY_MAX", "2")
    monkeypatch.setenv("AGENT_LLM_RETRY_BACKOFF_S", "0.3")
    obs = OpenAICompatibleLLMObserver.from_env(config=cfg)
    assert obs._timeout_s == 7.0  # noqa: SLF001
    assert obs._retry_max == 2  # noqa: SLF001
    assert obs._retry_backoff_s == 0.3  # noqa: SLF001
