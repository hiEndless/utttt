import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.feature_service.src.routes import create_router
from services.feature_service.src.providers.bundle import ProviderBundle
from services.feature_service.src.service import FeatureService
from services.feature_service.src.providers.noop import (
    NoopBehaviorProvider,
    NoopHorizonsProvider,
    NoopIndicatorsProvider,
    NoopOpenInterestProvider,
    NoopOrderbookProvider,
)
from services.feature_service.src.providers.future_source_providers import (
    NoopNewsProvider,
    NoopOnchainProvider,
    NoopSocialProvider,
)


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
                "alternative_sources": {
                    "news": {"source_type": "news", "available": False, "provider_state": "noop", "as_of_ms": None, "features": {}},
                    "social": {"source_type": "social", "available": False, "provider_state": "noop", "as_of_ms": None, "features": {}},
                    "onchain": {"source_type": "onchain", "available": False, "provider_state": "noop", "as_of_ms": None, "features": {}},
                },
            },
        }


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(create_router(_StubFeatureService()))
    return TestClient(app)


class _UnavailableFeatureService:
    async def get_raw_structure(self, exchange: str, symbol: str):
        from services.feature_service.src.service import FeatureDataUnavailableError

        raise FeatureDataUnavailableError(exchange=exchange, symbol=symbol, degraded_reasons=["horizons_provider_fallback"])

    async def get_features(self, exchange: str, symbol: str):
        from services.feature_service.src.service import FeatureDataUnavailableError

        raise FeatureDataUnavailableError(exchange=exchange, symbol=symbol, degraded_reasons=["open_interest_provider_fallback"])


class _OrderbookProvider:
    async def get_orderbook(self, exchange: str, symbol: str):
        _ = (exchange, symbol)
        return {"orderbook_snapshot": {"spread": 1.0}, "orderbook_structure_short": {"liquidity_stability": "stable"}}


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
    assert isinstance(body["data"]["alternative_sources"], dict)
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


def test_version_route_exposes_contract_meta():
    client = _build_client()
    resp = client.get("/internal/feature-service/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "feature_service"
    assert body["contract_version"] == "feature-contract-v1"
    assert body["response_schema_version"] == "1.0"
    assert isinstance(body["ts"], int)
    assert body["ts_ms"] == body["ts"]


def test_features_route_e2e_includes_alternative_source_semantics_fields():
    service = FeatureService.from_bundle(
        ProviderBundle(
            orderbook_provider=_OrderbookProvider(),
            open_interest_provider=NoopOpenInterestProvider(),
            horizons_provider=NoopHorizonsProvider(),
            behavior_provider=NoopBehaviorProvider(),
            indicators_provider=NoopIndicatorsProvider(),
            news_provider=NoopNewsProvider(),
            social_provider=NoopSocialProvider(),
            onchain_provider=NoopOnchainProvider(),
        )
    )
    app = FastAPI()
    app.include_router(create_router(service))
    client = TestClient(app)

    resp = client.get("/internal/feature-service/features/binance/ETHUSDT")
    assert resp.status_code == 200
    body = resp.json()
    alt = dict(body["data"].get("alternative_sources") or {})
    for src in ("news", "social", "onchain"):
        node = dict(alt.get(src) or {})
        assert node.get("source_type") == src
        assert node.get("data_source") == f"feature_service.{src}"
        assert node.get("inference_source") == "feature_service.normalizer"
