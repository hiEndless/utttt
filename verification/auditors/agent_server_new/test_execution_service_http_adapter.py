import asyncio
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.execution_service_http import HttpExecutionDecisionProvider


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = int(status_code)
        self._payload = dict(payload)
        self.request = httpx.Request("POST", "http://unit.test/internal/execution/decide")

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

    async def post(self, url: str, json):  # noqa: ANN001
        _ = (url, json)
        self._counter["calls"] += 1
        if not self._scripted:
            return _FakeResponse(200, {"ok": True})
        event = self._scripted.pop(0)
        if isinstance(event, Exception):
            raise event
        return event


def test_execution_http_provider_from_env_retry_config(monkeypatch):
    monkeypatch.setenv("AGENT_EXECUTION_BASE_URL", "http://127.0.0.1:9962/")
    monkeypatch.setenv("AGENT_EXECUTION_TIMEOUT_S", "12.5")
    monkeypatch.setenv("AGENT_EXECUTION_RETRY_MAX", "3")
    monkeypatch.setenv("AGENT_EXECUTION_RETRY_BACKOFF_S", "0.35")
    monkeypatch.setenv("AGENT_EXECUTION_RETRY_ON_STATUSES", "503, 429, x,503")

    provider = HttpExecutionDecisionProvider.from_env()

    assert provider._base_url == "http://127.0.0.1:9962"
    assert provider._timeout_s == 12.5
    assert provider._retry_max == 3
    assert provider._retry_backoff_s == 0.35
    assert provider._retry_on_statuses == (429, 503)


def test_execution_http_provider_retries_on_timeout_then_succeeds(monkeypatch):
    import services.agent_server_new.adapters.execution_service_http as mod

    counter = {"calls": 0}
    scripted = [httpx.TimeoutException("timeout"), _FakeResponse(200, {"execution_action": "add"})]
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda timeout: _FakeAsyncClient(scripted, counter))

    provider = HttpExecutionDecisionProvider(
        base_url="http://127.0.0.1:9962",
        timeout_s=1,
        retry_max=1,
        retry_backoff_s=0.0,
    )
    out = asyncio.run(provider.decide({"decision_id": "x"}))

    assert out["execution_action"] == "add"
    assert counter["calls"] == 2


def test_execution_http_provider_retries_on_retryable_http_status(monkeypatch):
    import services.agent_server_new.adapters.execution_service_http as mod

    counter = {"calls": 0}
    scripted = [_FakeResponse(503, {}), _FakeResponse(200, {"execution_action": "reduce"})]
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda timeout: _FakeAsyncClient(scripted, counter))

    provider = HttpExecutionDecisionProvider(
        base_url="http://127.0.0.1:9962",
        timeout_s=1,
        retry_max=1,
        retry_backoff_s=0.0,
        retry_on_statuses=(503,),
    )
    out = asyncio.run(provider.decide({"decision_id": "x"}))

    assert out["execution_action"] == "reduce"
    assert counter["calls"] == 2


def test_execution_http_provider_does_not_retry_non_retryable_http_status(monkeypatch):
    import services.agent_server_new.adapters.execution_service_http as mod

    counter = {"calls": 0}
    scripted = [_FakeResponse(400, {}), _FakeResponse(200, {"execution_action": "add"})]
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda timeout: _FakeAsyncClient(scripted, counter))

    provider = HttpExecutionDecisionProvider(
        base_url="http://127.0.0.1:9962",
        timeout_s=1,
        retry_max=3,
        retry_backoff_s=0.0,
        retry_on_statuses=(503,),
    )

    import pytest

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(provider.decide({"decision_id": "x"}))
    assert counter["calls"] == 1
