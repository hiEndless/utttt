import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from feature_service.routes import create_router


class _StubFeatureService:
    async def get_raw_structure(self, exchange: str, symbol: str):
        return {
            "exchange": exchange,
            "symbol": symbol,
            "degraded": True,
            "degraded_reasons": ["orderbook_provider_fallback"],
            "raw_market_structure": {
                "symbol": symbol,
                "candidate_horizons": ["short_term", "mid_term", "long_term"],
            },
        }

    async def get_features(self, exchange: str, symbol: str):
        return {
            "exchange": exchange,
            "symbol": symbol,
            "degraded": True,
            "degraded_reasons": ["indicators_provider_fallback"],
            "features": {
                "indicators": {"1m": {"rsi": 50.0}},
                "derived_metrics": {"candidate_horizons": ["short_term", "mid_term", "long_term"]},
                "structure_snapshot": {"pre_decision_structure": {}, "horizons": {}},
            },
        }


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(create_router(_StubFeatureService()))
    return TestClient(app)


class _UnavailableFeatureService:
    async def get_raw_structure(self, exchange: str, symbol: str):
        from feature_service.service import FeatureDataUnavailableError

        raise FeatureDataUnavailableError(exchange=exchange, symbol=symbol, degraded_reasons=["horizons_provider_fallback"])

    async def get_features(self, exchange: str, symbol: str):
        from feature_service.service import FeatureDataUnavailableError

        raise FeatureDataUnavailableError(exchange=exchange, symbol=symbol, degraded_reasons=["open_interest_provider_fallback"])


def test_raw_structure_route_returns_versioned_contract():
    client = _build_client()
    resp = client.get("/internal/feature-service/raw-structure/binance/ETHUSDT")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"meta", "data"}
    assert body["meta"]["schema_version"] == "1.0"
    assert isinstance(body["meta"]["generated_at_ms"], int)
    assert body["meta"]["degraded"] is True
    assert "orderbook_provider_fallback" in body["meta"]["degraded_reasons"]
    assert body["data"]["exchange"] == "binance"
    assert body["data"]["symbol"] == "ETHUSDT"
    assert "raw_market_structure" in body["data"]
    assert "raw_market_structure" not in body


def test_features_route_returns_versioned_contract():
    client = _build_client()
    resp = client.get("/internal/feature-service/features/binance/ETHUSDT")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"meta", "data"}
    assert body["meta"]["schema_version"] == "1.0"
    assert isinstance(body["meta"]["generated_at_ms"], int)
    assert body["meta"]["degraded"] is True
    assert "indicators_provider_fallback" in body["meta"]["degraded_reasons"]
    assert body["data"]["exchange"] == "binance"
    assert body["data"]["symbol"] == "ETHUSDT"
    assert isinstance(body["data"]["indicators"], dict)
    assert isinstance(body["data"]["derived_metrics"], dict)
    assert isinstance(body["data"]["structure_snapshot"], dict)
    assert "features" not in body


def test_routes_return_503_when_core_structure_unavailable():
    app = FastAPI()
    app.include_router(create_router(_UnavailableFeatureService()))
    client = TestClient(app)

    raw_resp = client.get("/internal/feature-service/raw-structure/binance/ETHUSDT")
    assert raw_resp.status_code == 503
    raw_detail = raw_resp.json().get("detail", {})
    assert raw_detail.get("code") == "feature_data_unavailable"
    assert "horizons_provider_fallback" in list(raw_detail.get("degraded_reasons") or [])

    feat_resp = client.get("/internal/feature-service/features/binance/ETHUSDT")
    assert feat_resp.status_code == 503
    feat_detail = feat_resp.json().get("detail", {})
    assert feat_detail.get("code") == "feature_data_unavailable"
    assert "open_interest_provider_fallback" in list(feat_detail.get("degraded_reasons") or [])
