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
    assert data["schema_mapping_version"] == "execution-schema-mapping-v7"


def test_decide_success() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/internal/execution/decide",
        json={
            "decision_id": "dec-001",
            "exchange": "binance",
            "account_id": "main",
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
    assert isinstance(data.get("signal_result"), dict)
    assert data["signal_result"]["mode"] == "simulated"
    assert data["signal_result"]["scope"]["account_id"] == "main"
    assert isinstance(data["signal_result"]["risk_checks"], list)


def test_decide_bad_request() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/internal/execution/decide",
        json={
            "decision_id": "dec-001",
            "exchange": "binance",
            "account_id": "main",
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
    assert data["account_id"] == "main"
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


def test_debug_state_with_account_id() -> None:
    client = TestClient(create_app())
    response = client.get("/internal/execution/debug/state/binance/ETHUSDT?account_id=sub_1")
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == "sub_1"
    assert data["position_state"]["account_id"] == "sub_1"
    assert data["account_state"]["account_id"] == "sub_1"


def test_debug_state_with_decision_id() -> None:
    client = TestClient(create_app())
    decide_resp = client.post(
        "/internal/execution/decide",
        json={
            "decision_id": "dec-debug-001",
            "exchange": "binance",
            "account_id": "main",
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
    assert data["decision_state"]["account_id"] == "main"
    assert data["decision_state"]["source"] == "execution_service"
    assert data["decision_state"]["trace_id"] == "trace-debug-001"
    assert isinstance(data["decision_state"].get("rule_debug"), dict)
    assert isinstance(data["decision_state"]["rule_debug"].get("hit_rule"), str)
    assert isinstance(data["decision_state"]["rule_debug"].get("matched_at_ms"), int)
    assert isinstance(data["decision_state"]["rule_debug"].get("evaluation_trace"), list)


def test_reconcile_sink_not_configured() -> None:
    client = TestClient(create_app())
    response = client.post("/internal/execution/reconcile", json={"order_id": "ord-001"})
    assert response.status_code == 503
    assert response.json()["detail"] == "execution_sink_not_configured"


def test_reconcile_mock_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXECUTION_SUBMIT_ENABLED", "true")
    monkeypatch.setenv("EXECUTION_SINK_MODE", "mock")
    client = TestClient(create_app())
    response = client.post(
        "/internal/execution/reconcile",
        json={
            "order_id": "mock-order-001",
            "decision_id": "dec-001",
            "exchange": "binance",
            "symbol": "ETHUSDT",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "mock"
    assert data["order_id"] == "mock-order-001"
    assert data["status"] == "filled"
    assert data["retry_meta"]["attempts"] == 1


def test_reconcile_writes_back_decision_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXECUTION_SUBMIT_ENABLED", "true")
    monkeypatch.setenv("EXECUTION_SINK_MODE", "mock")
    client = TestClient(create_app())

    decide_resp = client.post(
        "/internal/execution/decide",
        json={
            "decision_id": "dec-reconcile-001",
            "exchange": "binance",
            "account_id": "main",
            "symbol": "ETHUSDT",
            "direction_intent": "long",
            "confidence": {"level": "medium", "score": 0.66},
            "cross_horizon_policy": {"suggested_policy": "follow_long_term"},
            "risk_hints": {"agent_action_hint": "add"},
            "trace_id": "trace-reconcile-001",
        },
    )
    assert decide_resp.status_code == 200
    decide_data = decide_resp.json()
    assert isinstance(decide_data.get("order_result"), dict)
    order_id = str(decide_data["order_result"].get("order_id") or "")
    assert order_id

    reconcile_resp = client.post(
        "/internal/execution/reconcile",
        json={
            "order_id": order_id,
            "decision_id": "dec-reconcile-001",
            "exchange": "binance",
            "account_id": "main",
            "symbol": "ETHUSDT",
            "trace_id": "trace-reconcile-001",
        },
    )
    assert reconcile_resp.status_code == 200
    reconcile_data = reconcile_resp.json()
    assert reconcile_data["status"] == "filled"
    assert reconcile_data["account_id"] == "main"

    debug_resp = client.get("/internal/execution/debug/state/binance/ETHUSDT?decision_id=dec-reconcile-001")
    assert debug_resp.status_code == 200
    debug_data = debug_resp.json()
    assert isinstance(debug_data.get("decision_state"), dict)
    assert debug_data["decision_state"]["status"] == "filled"
    assert debug_data["decision_state"]["account_id"] == "main"
    assert debug_data["decision_state"]["last_transition"] == "filled"
    assert debug_data["decision_state"]["reconcile_order_id"] == order_id


def test_reconcile_order_id_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXECUTION_SUBMIT_ENABLED", "true")
    monkeypatch.setenv("EXECUTION_SINK_MODE", "mock")
    client = TestClient(create_app())
    payload = {
        "order_id": "mock-order-idem-001",
        "decision_id": "dec-idem-001",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
    }
    first = client.post("/internal/execution/reconcile", json=payload)
    assert first.status_code == 200
    first_data = first.json()
    assert first_data["idempotency_hit"] is False

    second = client.post("/internal/execution/reconcile", json=payload)
    assert second.status_code == 200
    second_data = second.json()
    assert second_data["idempotency_hit"] is True
    assert second_data["order_id"] == "mock-order-idem-001"
    assert second_data["ts"] == first_data["ts"]
