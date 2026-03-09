from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from execution_service.app import create_app


def test_healthz() -> None:
    client = TestClient(create_app())
    response = client.get("/internal/execution/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "execution_service"


def test_version() -> None:
    client = TestClient(create_app())
    response = client.get("/internal/execution/version")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "execution_service"
    assert data["contract_version"] == "execution-contract-v1"
    assert data["ruleset_version"] == "risk-rules-v1"
    assert data["state_machine_version"] == "execution-state-machine-v1"
    assert data["idempotency_version"] == "execution-idempotency-v1"
    assert data["schema_mapping_version"] == "execution-schema-mapping-v2"


def test_decide_success() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/internal/execution/decide",
        json={
            "decision_id": "dec-001",
            "exchange": "binance",
            "symbol": "ETHUSDT",
            "direction_intent": "long",
            "confidence": {"level": "medium", "score": 0.66},
            "cross_horizon_policy": {"suggested_policy": "reduce_risk"},
            "risk_hints": {"market_fragility": "medium"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision_id"] == "dec-001"
    assert data["execution_action"] in {"add", "reduce", "hold", "exit", "skip"}


def test_decide_bad_request() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/internal/execution/decide",
        json={
            "decision_id": "dec-001",
            "exchange": "binance",
            "symbol": "ETHUSDT",
            "direction_intent": "buy",
            "confidence": {"level": "medium", "score": 0.66},
            "cross_horizon_policy": {},
            "risk_hints": {},
        },
    )
    assert response.status_code == 400


def test_debug_state_success() -> None:
    client = TestClient(create_app())
    response = client.get("/internal/execution/debug/state/binance/ETHUSDT")
    assert response.status_code == 200
    data = response.json()
    assert data["exchange"] == "binance"
    assert data["symbol"] == "ETHUSDT"
    assert isinstance(data["position_state"], dict)
    assert isinstance(data["account_state"], dict)
    assert isinstance(data["risk_policy"], dict)


def test_debug_state_redacted() -> None:
    client = TestClient(create_app())
    response = client.get("/internal/execution/debug/state/binance/ETHUSDT?redact=true")
    assert response.status_code == 200
    data = response.json()
    assert data["redacted"] is True
    assert data["account_state"]["account_equity"] == "***"
    assert data["account_state"]["available_balance"] == "***"


def test_debug_state_with_decision_id() -> None:
    client = TestClient(create_app())
    decide_resp = client.post(
        "/internal/execution/decide",
        json={
            "decision_id": "dec-debug-001",
            "exchange": "binance",
            "symbol": "ETHUSDT",
            "direction_intent": "none",
            "confidence": {"level": "medium", "score": 0.66},
            "cross_horizon_policy": {},
            "risk_hints": {},
            "trace_id": "trace-debug-001",
        },
    )
    assert decide_resp.status_code == 200
    response = client.get("/internal/execution/debug/state/binance/ETHUSDT?decision_id=dec-debug-001")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get("decision_state"), dict)
    assert data["decision_state"]["decision_id"] == "dec-debug-001"
    assert data["decision_state"]["last_transition"] in {"decided", "skipped"}
    assert "attempts" in data["decision_state"]
    assert data["decision_state"]["source"] == "execution_service"
    assert data["decision_state"]["trace_id"] == "trace-debug-001"
