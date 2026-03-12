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


def test_http_readyz_returns_503_when_bootstrap_invalid(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("AGENT_ACTIVE_EVENTS_PROVIDER_MODE", "stub")
    app = create_app()
    client = TestClient(app)
    resp = client.get("/internal/agent/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["ok"] is False
    assert "workflow_bootstrap_failed" in list(body.get("errors") or [])

