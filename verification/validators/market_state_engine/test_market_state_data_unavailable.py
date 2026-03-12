import asyncio
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = "/Users/lichaoyuan/Desktop/UTaker"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.market_state_engine.src.errors import FeatureDataUnavailableFromUpstreamError
from services.market_state_engine.src.routes import create_router
from services.market_state_engine.src.service import MarketStateService


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


class _AlternativeSourceRawProvider:
    async def get_raw_structure(self, exchange: str, symbol: str):
        return {
            "symbol": symbol,
            "horizons": {},
            "orderbook": {},
            "open_interest": {},
            "behavioral": {},
            "alternative_sources": {
                "news": {
                    "source_type": "news",
                    "available": True,
                    "provider_state": "primary",
                    "as_of_ms": 1700000000000,
                    "features": {"headline_score": 0.7},
                }
            },
        }


class _AlternativeSourceRawProviderNoopAvailable:
    async def get_raw_structure(self, exchange: str, symbol: str):
        return {
            "symbol": symbol,
            "horizons": {},
            "orderbook": {},
            "open_interest": {},
            "behavioral": {},
            "alternative_sources": {
                "news": {
                    "source_type": "news",
                    "available": True,
                    "provider_state": "noop",
                    "as_of_ms": None,
                    "features": {},
                }
            },
        }


class _CapturingEngine:
    def __init__(self) -> None:
        self.last_market_structure = None

    def build(self, exchange: str, symbol: str, market_structure: dict):
        self.last_market_structure = dict(market_structure or {})
        alt = dict((market_structure or {}).get("alternative_sources") or {})

        class _FeaturesWithAltEvidence:
            anomalies = {"flags": []}

            def to_dict(self_nonlocal):  # noqa: ANN001
                return {"status": "ok", "evidence": {"alternative_sources": dict(alt)}}

        return _FakeMsl(), _FeaturesWithAltEvidence()

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
                "source": {"name": "event_center_new", "category": "technical"},
                "trace": {"schema_version": "selected-v2"},
                "route": {"to": "market_state_engine"},
            }
        ]


class _SelectedEventProviderFail:
    async def get_selected_events(self, exchange: str, symbol: str, *, limit: int = 20):
        raise RuntimeError("boom")


class _SelectedEventProviderMissingTraceVersion:
    async def get_selected_events(self, exchange: str, symbol: str, *, limit: int = 20):
        return [
            {
                "asset": f"{exchange}:{symbol}",
                "ts_ms": 1234567890,
                "selected_type": "breakout_signal",
                "direction_hint": "bullish",
                "priority": "high",
                "context_snapshot": {"x": 1},
                "trace": {},
                "route": {"to": "market_state_engine"},
            }
        ]


class _SelectedEventProviderWithAlternativeSummary:
    async def get_selected_events(self, exchange: str, symbol: str, *, limit: int = 20):
        return [
            {
                "asset": f"{exchange}:{symbol}",
                "ts_ms": 1234567890,
                "selected_type": "onchain_alert",
                "direction_hint": "mixed",
                "priority": "medium",
                "context_snapshot": {
                    "alternative_sources_summary": {
                        "available_sources": ["onchain"],
                        "unavailable_sources": ["news", "social"],
                        "provider_states": {"news": "empty", "social": "empty", "onchain": "event_evidence_present"},
                        "feature_keys": {"news": [], "social": [], "onchain": ["inflow_usd"]},
                        "evidence_counts": {"news": 0, "social": 0, "onchain": 2},
                    }
                },
                "trace": {"schema_version": "selected-v2"},
                "route": {"to": "market_state_engine"},
            }
        ]


class _SelectedEventProviderWithAlternativeSummaryMissingSources:
    async def get_selected_events(self, exchange: str, symbol: str, *, limit: int = 20):
        return [
            {
                "asset": f"{exchange}:{symbol}",
                "ts_ms": 1234567890,
                "selected_type": "onchain_alert",
                "direction_hint": "mixed",
                "priority": "medium",
                "context_snapshot": {
                    "alternative_sources_summary": {
                        "available_sources": ["onchain"],
                        "unavailable_sources": ["news", "social"],
                        "provider_states": {"news": "empty", "social": "empty", "onchain": "event_evidence_present"},
                        "feature_keys": {"news": [], "social": [], "onchain": ["inflow_usd"]},
                        "evidence_counts": {"news": 0, "social": 0, "onchain": 2},
                    }
                },
                "trace": {"schema_version": "selected-v2"},
                "route": {"to": "market_state_engine"},
            }
        ]


class _SelectedEventProviderWithNewsAlternativeSummary:
    async def get_selected_events(self, exchange: str, symbol: str, *, limit: int = 20):
        return [
            {
                "asset": f"{exchange}:{symbol}",
                "ts_ms": 1234567890,
                "selected_type": "news.alert",
                "direction_hint": "mixed",
                "priority": "medium",
                "context_snapshot": {
                    "alternative_sources_summary": {
                        "available_sources": ["news"],
                        "unavailable_sources": ["social", "onchain"],
                        "provider_states": {"news": "event_evidence_present", "social": "empty", "onchain": "empty"},
                        "feature_keys": {"news": ["headline_score"], "social": [], "onchain": []},
                        "evidence_counts": {"news": 2, "social": 0, "onchain": 0},
                    }
                },
                "trace": {"schema_version": "selected-v2"},
                "route": {"to": "market_state_engine"},
            }
        ]


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
        semantic_contract = dict((out.get("state_features") or {}).get("semantic_contract") or {})
        assert semantic_contract.get("horizon_confidence", {}).get("canonical_field") == "horizons.{hz}.confidence"
        assert semantic_contract.get("horizon_confidence", {}).get("compat_alias") == "horizons.{hz}.horizon_confidence"
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
    assert isinstance(body["ts"], int)
    assert body["ts_ms"] == body["ts"]


def test_market_state_route_healthz_exposes_ts_ms_alias():
    app = FastAPI()
    service = MarketStateService(raw_structure_provider=_OkRawProvider())
    app.include_router(create_router(service))
    client = TestClient(app)

    resp = client.get("/internal/market-state/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["service"] == "market_state_engine"
    assert isinstance(body["ts"], int)
    assert body["ts_ms"] == body["ts"]


def test_market_state_route_version_exposes_contract_meta():
    app = FastAPI()
    service = MarketStateService(raw_structure_provider=_OkRawProvider())
    app.include_router(create_router(service))
    client = TestClient(app)

    resp = client.get("/internal/market-state/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "market_state_engine"
    assert body["contract_version"] == "market-state-contract-v1"
    assert body["msl_schema_version"] == 2
    assert isinstance(body["ts"], int)
    assert body["ts_ms"] == body["ts"]


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


def test_market_state_service_keeps_alternative_sources_in_evidence():
    async def _run():
        service = MarketStateService(raw_structure_provider=_AlternativeSourceRawProvider())
        capturing_engine = _CapturingEngine()
        service._engine = capturing_engine

        out = await service.get_market_state("binance", "ETHUSDT")
        assert out["status"] == "ok"
        assert "external_event_input_ignored" not in list(out.get("anomaly_flags") or [])
        assert isinstance(capturing_engine.last_market_structure, dict)
        assert "alternative_sources" in capturing_engine.last_market_structure

        alt = ((out.get("state_features") or {}).get("evidence") or {}).get("alternative_sources") or {}
        assert alt.get("news", {}).get("source_type") == "news"
        assert alt.get("news", {}).get("provider_state") == "primary"
        assert alt.get("social", {}).get("source_type") == "social"
        assert alt.get("onchain", {}).get("source_type") == "onchain"

    asyncio.run(_run())


def test_market_state_service_builds_alternative_sources_fusion():
    async def _run():
        service = MarketStateService(
            raw_structure_provider=_AlternativeSourceRawProvider(),
            selected_event_provider=_SelectedEventProviderWithAlternativeSummary(),
        )
        out = await service.get_market_state("binance", "ETHUSDT")
        evidence = ((out.get("state_features") or {}).get("evidence") or {})
        fusion = dict(evidence.get("alternative_sources_fusion") or {})
        merged = dict((fusion.get("merged") or {}).get("by_source") or {})
        assert fusion.get("preferred_source") == "feature"
        assert merged.get("news", {}).get("available") is True
        assert merged.get("onchain", {}).get("available") is True
        assert merged.get("onchain", {}).get("event_evidence_count") == 2
        assert merged.get("news", {}).get("data_source") == "feature_service.news"
        assert merged.get("news", {}).get("inference_source") == "feature_service.normalizer"
        assert merged.get("onchain", {}).get("data_source") == "event_center_new.onchain"
        assert merged.get("onchain", {}).get("inference_source") == "event_center_new.selector"
        assert isinstance(fusion.get("conflicts"), list)

    asyncio.run(_run())


def test_market_state_service_builds_alternative_sources_fusion_with_default_sources_when_missing():
    async def _run():
        service = MarketStateService(
            raw_structure_provider=_AlternativeSourceRawProvider(),
            selected_event_provider=_SelectedEventProviderWithAlternativeSummaryMissingSources(),
        )
        out = await service.get_market_state("binance", "ETHUSDT")
        evidence = ((out.get("state_features") or {}).get("evidence") or {})
        fusion = dict(evidence.get("alternative_sources_fusion") or {})
        merged = dict((fusion.get("merged") or {}).get("by_source") or {})
        assert merged.get("onchain", {}).get("data_source") == "event_center_new.onchain"
        assert merged.get("onchain", {}).get("inference_source") == "event_center_new.selector"
        assert merged.get("news", {}).get("data_source") == "feature_service.news"
        assert merged.get("news", {}).get("inference_source") == "feature_service.normalizer"

    asyncio.run(_run())


def test_market_state_service_treats_noop_feature_source_as_unavailable_in_fusion():
    async def _run():
        service = MarketStateService(
            raw_structure_provider=_AlternativeSourceRawProviderNoopAvailable(),
            selected_event_provider=_SelectedEventProviderWithNewsAlternativeSummary(),
        )
        out = await service.get_market_state("binance", "ETHUSDT")
        evidence = ((out.get("state_features") or {}).get("evidence") or {})
        fusion = dict(evidence.get("alternative_sources_fusion") or {})
        merged = dict((fusion.get("merged") or {}).get("by_source") or {})
        news = dict(merged.get("news") or {})
        assert news.get("feature_available") is False
        assert news.get("event_available") is True
        assert news.get("data_source") == "event_center_new.news"
        assert news.get("inference_source") == "event_center_new.selector"
        assert fusion.get("preferred_source") == "event_center"

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
        assert "event_center_new" in list(evidence.get("selected_event_sources") or [])
        assert "selected-v2" in list(evidence.get("selected_event_schema_versions") or [])
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


def test_market_state_service_marks_unversioned_selected_events():
    async def _run():
        service = MarketStateService(
            raw_structure_provider=_OkRawProvider(),
            selected_event_provider=_SelectedEventProviderMissingTraceVersion(),
        )
        service._engine = _FakeEngine()
        out = await service.get_market_state("binance", "ETHUSDT")
        evidence = ((out.get("state_features") or {}).get("evidence") or {})
        assert evidence.get("selected_events_count") == 1
        assert evidence.get("selected_events_unversioned_count") == 1
        assert "selected_events_unversioned" in list(out.get("anomaly_flags") or [])

    asyncio.run(_run())


def test_market_state_service_logs_alert_for_unversioned_selected_events(monkeypatch):
    async def _run():
        import services.market_state_engine.src.service as mod

        captured = []

        def _fake_warning(msg, *args, **kwargs):  # noqa: ANN001, ARG001
            text = str(msg)
            if args:
                text = text % args
            captured.append(text)

        monkeypatch.setattr(mod.logger, "warning", _fake_warning)
        service = MarketStateService(
            raw_structure_provider=_OkRawProvider(),
            selected_event_provider=_SelectedEventProviderMissingTraceVersion(),
        )
        service._engine = _FakeEngine()
        out = await service.get_market_state("binance", "ETHUSDT")
        assert out.get("status") == "ok"
        assert any("MSE_SELECTED_EVENTS_UNVERSIONED" in line for line in captured)

    asyncio.run(_run())
