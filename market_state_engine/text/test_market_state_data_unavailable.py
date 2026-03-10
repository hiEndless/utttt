import asyncio
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = "/Users/lichaoyuan/Desktop/UTaker"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from market_state_engine.errors import FeatureDataUnavailableFromUpstreamError
from market_state_engine.routes import create_router
from market_state_engine.service import MarketStateService


class _UnavailableRawProvider:
    async def get_raw_structure(self, exchange: str, symbol: str):
        raise FeatureDataUnavailableFromUpstreamError(
            exchange=exchange,
            symbol=symbol,
            degraded_reasons=["feature_data_unavailable", "orderbook_provider_fallback"],
        )


class _OkRawProvider:
    async def get_raw_structure(self, exchange: str, symbol: str):
        return {"symbol": symbol, "horizons": {}, "orderbook": {}, "open_interest": {}, "behavioral": {}}


class _FakeMsl:
    def to_llm_dict(self):
        return {"summary": "ok", "anomalies": []}


class _FakeFeatures:
    anomalies = {"flags": []}

    def to_dict(self):
        return {"status": "ok"}


class _FakeEngine:
    def build(self, exchange: str, symbol: str, market_structure: dict):
        return _FakeMsl(), _FakeFeatures()

    def get_last_msl_meta(self):
        return {"schema_version": 2, "inference_version": "msl_generator_v1", "inference_profile": "default"}

    def infer_multi_horizon_msl(self, *, features):  # noqa: ANN001
        return (
            {"short_term": {}, "mid_term": {}, "long_term": {}},
            {"short_term": {}, "mid_term": {}, "long_term": {}},
            {"alignment": "unknown", "conflicts": [], "suggested_policy": "no_action", "policy_reason": "insufficient_evidence"},
        )


class _ExternalMixedRawProvider:
    async def get_raw_structure(self, exchange: str, symbol: str):
        return {
            "symbol": symbol,
            "horizons": {},
            "orderbook": {},
            "open_interest": {},
            "behavioral": {},
            "news": {"headline": "x"},
            "social": {"hot": True},
            "onchain": {"whale_flow": 1},
        }


class _CapturingEngine:
    def __init__(self) -> None:
        self.last_market_structure = None

    def build(self, exchange: str, symbol: str, market_structure: dict):
        self.last_market_structure = dict(market_structure or {})
        return _FakeMsl(), _FakeFeatures()

    def get_last_msl_meta(self):
        return {}

    def infer_multi_horizon_msl(self, *, features):  # noqa: ANN001
        return {}, {}, {"alignment": "unknown", "conflicts": [], "suggested_policy": "no_action", "policy_reason": "insufficient_evidence"}


class _SelectedEventProviderOk:
    async def get_selected_events(self, exchange: str, symbol: str, *, limit: int = 20):
        return [
            {
                "asset": f"{exchange}:{symbol}",
                "ts_ms": 1234567890,
                "selected_type": "breakout_signal",
                "direction_hint": "bullish",
                "priority": "high",
                "context_snapshot": {"x": 1},
                "route": {"to": "market_state_engine"},
            }
        ]


class _SelectedEventProviderFail:
    async def get_selected_events(self, exchange: str, symbol: str, *, limit: int = 20):
        raise RuntimeError("boom")


def test_market_state_service_short_circuit_on_data_unavailable():
    async def _run():
        service = MarketStateService(raw_structure_provider=_UnavailableRawProvider())
        out = await service.get_market_state("binance", "ETHUSDT")
        assert out["status"] == "data_unavailable"
        assert out["reason_code"] == "feature_data_unavailable"
        assert "orderbook_provider_fallback" in list(out.get("degraded_reasons") or [])
        assert out["anomaly_flags"] == ["data_unavailable"]
        assert out["msl_meta"]["inference_version"] == "short_circuit_unavailable"
        assert out["cross_horizon"]["suggested_policy"] == "no_action"
        assert isinstance(out.get("msl"), dict)
        assert "sentiment_state" not in out["msl"]
        assert out["msl"]["summary"].startswith("上游 feature_service")

    asyncio.run(_run())


def test_market_state_service_ok_status():
    async def _run():
        service = MarketStateService(raw_structure_provider=_OkRawProvider())
        # 用假引擎隔离本测试，专注验证状态契约字段。
        service._engine = _FakeEngine()
        out = await service.get_market_state("binance", "ETHUSDT")
        assert out["status"] == "ok"
        assert out["exchange"] == "binance"
        assert out["symbol"] == "ETHUSDT"
        assert isinstance(out.get("msl_meta"), dict)
        assert isinstance(out.get("msl_bundle"), dict)
        assert isinstance(out.get("cross_horizon"), dict)
        assert "suggested_policy" in out.get("cross_horizon")
        assert "reason_code" not in out
        assert "sentiment_state" not in dict(out.get("msl") or {})

    asyncio.run(_run())


def test_market_state_route_returns_200_with_data_unavailable_status():
    app = FastAPI()
    service = MarketStateService(raw_structure_provider=_UnavailableRawProvider())
    app.include_router(create_router(service))
    client = TestClient(app)

    resp = client.get("/internal/market-state/binance/ETHUSDT")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "data_unavailable"
    assert body["reason_code"] == "feature_data_unavailable"
    assert "orderbook_provider_fallback" in list(body.get("degraded_reasons") or [])


def test_market_state_route_returns_ok_status():
    app = FastAPI()
    service = MarketStateService(raw_structure_provider=_OkRawProvider())
    service._engine = _FakeEngine()
    app.include_router(create_router(service))
    client = TestClient(app)

    resp = client.get("/internal/market-state/binance/ETHUSDT")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["exchange"] == "binance"
    assert body["symbol"] == "ETHUSDT"


def test_market_state_service_ignores_external_event_fields():
    async def _run():
        service = MarketStateService(raw_structure_provider=_ExternalMixedRawProvider())
        capturing_engine = _CapturingEngine()
        service._engine = capturing_engine

        out = await service.get_market_state("binance", "ETHUSDT")
        assert out["status"] == "ok"
        assert "external_event_input_ignored" in list(out.get("anomaly_flags") or [])
        assert "external_event_input_ignored" in list((out.get("msl") or {}).get("anomalies") or [])

        # 对外返回与传入引擎的 market_structure 均不应携带外部事件字段。
        assert "news" not in dict(out.get("raw_market_structure") or {})
        assert "social" not in dict(out.get("raw_market_structure") or {})
        assert "onchain" not in dict(out.get("raw_market_structure") or {})
        assert isinstance(capturing_engine.last_market_structure, dict)
        assert "news" not in capturing_engine.last_market_structure
        assert "social" not in capturing_engine.last_market_structure
        assert "onchain" not in capturing_engine.last_market_structure

        ignored = ((out.get("state_features") or {}).get("evidence") or {}).get("ignored_external_input_keys") or []
        assert "news" in ignored and "social" in ignored and "onchain" in ignored

    asyncio.run(_run())


def test_market_state_service_loads_plugin_profile_from_env(monkeypatch):
    monkeypatch.setenv("MSE_STATE_PLUGIN_PROFILE", "fast_mode")
    monkeypatch.setenv("MSE_STATE_PLUGIN_PROFILES_FILE", "/tmp/state_inference_profiles.json")
    monkeypatch.setenv("MSE_MSL_INFERENCE_VERSION", "msl_generator_v2")
    monkeypatch.setenv("MSE_STATE_PLUGINS_ENABLED", "regime_inference,structure_inference")
    monkeypatch.setenv("MSE_STATE_PLUGINS_DISABLED", "structure_inference")
    cfg = MarketStateService._load_state_inference_config()
    assert cfg["plugin_profile"] == "fast_mode"
    assert cfg["profiles_file"] == "/tmp/state_inference_profiles.json"
    assert cfg["inference_version"] == "msl_generator_v2"
    assert cfg["enabled_plugins"] == ["regime_inference", "structure_inference"]
    assert cfg["disabled_plugins"] == ["structure_inference"]


def test_market_state_service_exposes_msl_meta_with_inference_version(monkeypatch):
    async def _run():
        monkeypatch.setenv("MSE_MSL_INFERENCE_VERSION", "msl_generator_v2")
        service = MarketStateService(raw_structure_provider=_OkRawProvider())
        out = await service.get_market_state("binance", "ETHUSDT")
        meta = dict(out.get("msl_meta") or {})
        assert meta.get("schema_version") == 2
        assert meta.get("inference_version") == "msl_generator_v2"
        assert meta.get("inference_profile") in {"default", "fast_mode", "risk_only"}

    asyncio.run(_run())


def test_market_state_service_attaches_selected_event_evidence():
    async def _run():
        service = MarketStateService(
            raw_structure_provider=_OkRawProvider(),
            selected_event_provider=_SelectedEventProviderOk(),
        )
        service._engine = _FakeEngine()
        out = await service.get_market_state("binance", "ETHUSDT")
        evidence = ((out.get("state_features") or {}).get("evidence") or {})
        assert evidence.get("selected_events_count") == 1
        assert "breakout_signal" in list(evidence.get("selected_event_types") or [])
        assert "selected_event_context_attached" in list(out.get("anomaly_flags") or [])

    asyncio.run(_run())


def test_market_state_service_selected_event_provider_failure_is_degraded_not_crash():
    async def _run():
        service = MarketStateService(
            raw_structure_provider=_OkRawProvider(),
            selected_event_provider=_SelectedEventProviderFail(),
        )
        service._engine = _FakeEngine()
        out = await service.get_market_state("binance", "ETHUSDT")
        evidence = ((out.get("state_features") or {}).get("evidence") or {})
        assert evidence.get("selected_events_unavailable") is True
        assert "selected_events_unavailable" in list(out.get("anomaly_flags") or [])

    asyncio.run(_run())
