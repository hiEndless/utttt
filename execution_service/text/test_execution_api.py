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
