from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.app.http_app import create_app


def test_http_healthz_ok() -> None:
    app = create_app()
    client = TestClient(app)
    resp = client.get("/internal/agent/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["service"] == "agent_server_new"


def test_http_version_ok() -> None:
    app = create_app()
    client = TestClient(app)
    resp = client.get("/internal/agent/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "agent_server_new"
    assert body["contract_version"] == "agent-contract-v1"
    assert body["runtime_version"] == "agent-runtime-v1"


def test_http_readyz_returns_503_when_bootstrap_invalid(monkeypatch) -> None:  # noqa: ANN001
    import services.agent_server_new.app.http_app as mod

    monkeypatch.setenv("AGENT_ACTIVE_EVENTS_PROVIDER_MODE", "stub")
    monkeypatch.setattr(
        mod,
        "create_trade_event_workflow_from_env",
        lambda: (_ for _ in ()).throw(RuntimeError("[AGENT_BOOTSTRAP_MINIMAL_EXECUTION_REQUIRED] minimal mode requires execution")),
    )
    app = create_app()
    client = TestClient(app)
    resp = client.get("/internal/agent/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["ok"] is False
    assert body["status_level"] == "red"
    assert "workflow_bootstrap_failed" in list(body.get("errors") or [])
    assert "AGENT_BOOTSTRAP_MINIMAL_EXECUTION_REQUIRED" in list(body.get("errors") or [])


def test_http_readyz_upstream_warning_in_non_strict_mode(monkeypatch) -> None:  # noqa: ANN001
    import services.agent_server_new.app.http_app as mod

    monkeypatch.setenv("AGENT_READY_CHECK_UPSTREAM_STRICT", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_MARKET_STATE", "true")
    monkeypatch.setenv("AGENT_READY_CHECK_ACTIVE_EVENTS_REDIS", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_EVENT_RECORDER", "false")
    monkeypatch.setattr(mod, "_check_market_state_healthz", lambda timeout_s: (False, {"error": "down"}))
    monkeypatch.setattr(mod, "create_trade_event_workflow_from_env", lambda: object())
    app = create_app()
    client = TestClient(app)
    resp = client.get("/internal/agent/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["status_level"] == "yellow"
    assert "market_state_unreachable" in list(body.get("warnings") or [])
    assert "market_state_unreachable" not in list(body.get("errors") or [])


def test_http_readyz_upstream_error_in_strict_mode(monkeypatch) -> None:  # noqa: ANN001
    import services.agent_server_new.app.http_app as mod

    monkeypatch.setenv("AGENT_READY_CHECK_UPSTREAM_STRICT", "true")
    monkeypatch.setenv("AGENT_READY_CHECK_MARKET_STATE", "true")
    monkeypatch.setenv("AGENT_READY_CHECK_ACTIVE_EVENTS_REDIS", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_EVENT_RECORDER", "false")
    monkeypatch.setattr(mod, "_check_market_state_healthz", lambda timeout_s: (False, {"error": "down"}))
    monkeypatch.setattr(mod, "create_trade_event_workflow_from_env", lambda: object())
    app = create_app()
    client = TestClient(app)
    resp = client.get("/internal/agent/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["ok"] is False
    assert body["status_level"] == "red"
    assert "market_state_unreachable" in list(body.get("errors") or [])


def test_http_readyz_green_when_checks_pass(monkeypatch) -> None:  # noqa: ANN001
    import services.agent_server_new.app.http_app as mod

    monkeypatch.setenv("AGENT_READY_CHECK_UPSTREAM_STRICT", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_MARKET_STATE", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_EXECUTION_SERVICE", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_ACTIVE_EVENTS_REDIS", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_EVENT_RECORDER", "false")
    monkeypatch.setattr(mod, "create_trade_event_workflow_from_env", lambda: object())
    app = create_app()
    client = TestClient(app)
    resp = client.get("/internal/agent/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["status_level"] == "green"


def test_http_readyz_recorder_warning_in_non_strict_mode(monkeypatch) -> None:  # noqa: ANN001
    import services.agent_server_new.app.http_app as mod

    monkeypatch.setenv("AGENT_READY_CHECK_UPSTREAM_STRICT", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_MARKET_STATE", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_ACTIVE_EVENTS_REDIS", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_EVENT_RECORDER", "true")
    monkeypatch.setattr(mod, "_check_event_recorder_writable", lambda: (False, {"error": "permission"}))
    monkeypatch.setattr(mod, "create_trade_event_workflow_from_env", lambda: object())
    app = create_app()
    client = TestClient(app)
    resp = client.get("/internal/agent/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "event_recorder_unwritable" in list(body.get("warnings") or [])


def test_http_readyz_recorder_error_in_strict_mode(monkeypatch) -> None:  # noqa: ANN001
    import services.agent_server_new.app.http_app as mod

    monkeypatch.setenv("AGENT_READY_CHECK_UPSTREAM_STRICT", "true")
    monkeypatch.setenv("AGENT_READY_CHECK_MARKET_STATE", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_ACTIVE_EVENTS_REDIS", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_EVENT_RECORDER", "true")
    monkeypatch.setattr(mod, "_check_event_recorder_writable", lambda: (False, {"error": "permission"}))
    monkeypatch.setattr(mod, "create_trade_event_workflow_from_env", lambda: object())
    app = create_app()
    client = TestClient(app)
    resp = client.get("/internal/agent/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["ok"] is False
    assert "event_recorder_unwritable" in list(body.get("errors") or [])


def test_http_readyz_execution_warning_in_non_strict_mode(monkeypatch) -> None:  # noqa: ANN001
    import services.agent_server_new.app.http_app as mod

    monkeypatch.setenv("AGENT_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("AGENT_READY_CHECK_UPSTREAM_STRICT", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_MARKET_STATE", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_ACTIVE_EVENTS_REDIS", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_EVENT_RECORDER", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_EXECUTION_SERVICE", "true")
    monkeypatch.setattr(mod, "_check_execution_service_healthz", lambda timeout_s: (False, {"error": "down"}))
    monkeypatch.setattr(mod, "create_trade_event_workflow_from_env", lambda: object())
    app = create_app()
    client = TestClient(app)
    resp = client.get("/internal/agent/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "execution_service_unreachable" in list(body.get("warnings") or [])


def test_http_readyz_execution_error_in_strict_mode(monkeypatch) -> None:  # noqa: ANN001
    import services.agent_server_new.app.http_app as mod

    monkeypatch.setenv("AGENT_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("AGENT_READY_CHECK_UPSTREAM_STRICT", "true")
    monkeypatch.setenv("AGENT_READY_CHECK_MARKET_STATE", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_ACTIVE_EVENTS_REDIS", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_EVENT_RECORDER", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_EXECUTION_SERVICE", "true")
    monkeypatch.setattr(mod, "_check_execution_service_healthz", lambda timeout_s: (False, {"error": "down"}))
    monkeypatch.setattr(mod, "create_trade_event_workflow_from_env", lambda: object())
    app = create_app()
    client = TestClient(app)
    resp = client.get("/internal/agent/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["ok"] is False
    assert "execution_service_unreachable" in list(body.get("errors") or [])


def test_http_readyz_low_disk_warning_in_non_strict_mode(monkeypatch) -> None:  # noqa: ANN001
    import services.agent_server_new.app.http_app as mod

    monkeypatch.setenv("AGENT_EVENT_RECORDER_MODE", "jsonl")
    monkeypatch.setenv("AGENT_READY_CHECK_UPSTREAM_STRICT", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_MARKET_STATE", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_EXECUTION_SERVICE", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_ACTIVE_EVENTS_REDIS", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_EVENT_RECORDER", "true")
    monkeypatch.setattr(mod, "_check_event_recorder_writable", lambda: (True, {"path": "x"}))
    monkeypatch.setattr(
        mod,
        "_check_event_recorder_disk_free",
        lambda min_free_bytes: (False, {"free_bytes": 1, "min_free_bytes": min_free_bytes}),
    )
    monkeypatch.setattr(mod, "create_trade_event_workflow_from_env", lambda: object())
    app = create_app()
    client = TestClient(app)
    resp = client.get("/internal/agent/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "event_recorder_low_disk" in list(body.get("warnings") or [])


def test_http_readyz_low_disk_error_in_strict_mode(monkeypatch) -> None:  # noqa: ANN001
    import services.agent_server_new.app.http_app as mod

    monkeypatch.setenv("AGENT_EVENT_RECORDER_MODE", "jsonl")
    monkeypatch.setenv("AGENT_READY_CHECK_UPSTREAM_STRICT", "true")
    monkeypatch.setenv("AGENT_READY_CHECK_MARKET_STATE", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_EXECUTION_SERVICE", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_ACTIVE_EVENTS_REDIS", "false")
    monkeypatch.setenv("AGENT_READY_CHECK_EVENT_RECORDER", "true")
    monkeypatch.setattr(mod, "_check_event_recorder_writable", lambda: (True, {"path": "x"}))
    monkeypatch.setattr(
        mod,
        "_check_event_recorder_disk_free",
        lambda min_free_bytes: (False, {"free_bytes": 1, "min_free_bytes": min_free_bytes}),
    )
    monkeypatch.setattr(mod, "create_trade_event_workflow_from_env", lambda: object())
    app = create_app()
    client = TestClient(app)
    resp = client.get("/internal/agent/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["ok"] is False
    assert "event_recorder_low_disk" in list(body.get("errors") or [])
