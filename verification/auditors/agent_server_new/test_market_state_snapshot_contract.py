import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent_server_new.adapters.market_state_http import HttpMarketStateProvider, _build_msl_from_dict
from agent_server_new.app.context_builder import ContextBuilder
from agent_server_new.ports.market_state import MarketStateSnapshot


def _sample_msl() -> dict:
    return {
        "version": 2,
        "timestamp": "2026-03-09T12:00:00Z",
        "symbol": "ETHUSDT",
        "market_regime": {"trend": "bullish", "phase": "continuation", "timeframe_alignment": "aligned", "strength": 0.7},
        "liquidity_state": {"dominant_pressure": "buyers", "liquidity_risk": "neutral", "orderbook_bias": "neutral", "liquidation_proximity": "none"},
        "positioning_state": {"crowding": "balanced", "whale_bias": "unknown", "retail_bias": "unknown", "oi_trend": "expanding"},
        "volatility_state": {"volatility_regime": "normal", "expansion_risk": "unknown", "volatility_direction": "upside"},
        "risk_state": {"cascade_risk": "low", "squeeze_probability": "low", "reversal_risk": "low"},
        "market_structure_state": {"support_strength": "unknown", "resistance_strength": "unknown", "range_state": "breakout", "trend_structure": "hh_hl"},
        "key_levels": {"major_support": [], "major_resistance": [], "liquidation_clusters": []},
        "anomalies": [],
        "summary": "ok",
    }


def test_http_market_state_provider_parses_cross_horizon(monkeypatch):
    payload = {
        "exchange": "binance",
        "symbol": "ETHUSDT",
        "msl": _sample_msl(),
        "msl_meta": {"schema_version": 2, "inference_version": "msl_generator_v2"},
        "msl_bundle": {"short_term": {}, "mid_term": {}, "long_term": {}},
        "msl_bundle_meta": {"short_term": {}, "mid_term": {}, "long_term": {}},
        "cross_horizon": {"alignment": "conflicting", "suggested_policy": "wait_confirmation"},
        "state_features": {},
        "anomaly_flags": [],
        "raw_market_structure": {},
    }

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class _Client:
        def __init__(self, *args, **kwargs):  # noqa: ANN003
            _ = (args, kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            _ = (exc_type, exc, tb)
            return False

        async def get(self, url: str):
            _ = url
            return _Resp()

    import agent_server_new.adapters.market_state_http as mod

    monkeypatch.setattr(mod.httpx, "AsyncClient", _Client)

    async def _run():
        provider = HttpMarketStateProvider("http://127.0.0.1:8080")
        snap = await provider.get_market_state("binance", "ETHUSDT")
        assert snap.msl_meta.get("schema_version") == 2
        assert snap.cross_horizon.get("suggested_policy") == "wait_confirmation"
        assert set(snap.msl_bundle.keys()) == {"short_term", "mid_term", "long_term"}

    asyncio.run(_run())


def test_context_builder_injects_cross_horizon_feature():
    class _MarketState:
        async def get_market_state(self, exchange: str, symbol: str):
            _ = (exchange, symbol)
            return MarketStateSnapshot(
                exchange="binance",
                symbol="ETHUSDT",
                msl=_build_msl_from_dict(_sample_msl()),
                msl_meta={"schema_version": 2, "inference_version": "msl_generator_v2"},
                cross_horizon={"alignment": "mixed", "suggested_policy": "reduce_risk"},
                state_features={"evidence": {}, "anomalies": {}},
            )

    class _Position:
        async def get_position_context(self, exchange: str, symbol: str):
            _ = (exchange, symbol)
            return {}

    class _Events:
        async def get_active_events(self, exchange: str, symbol: str):
            _ = (exchange, symbol)
            return []

    async def _run():
        builder = ContextBuilder(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            max_key_features=5,
        )
        built = await builder.build(
            event_id="evt-1",
            exchange="binance",
            symbol="ETHUSDT",
            signal_payload={"event_type": "indicator_signal"},
        )
        features = list((built.ctx.key_market_features or {}).get("features") or [])
        by_name = {str(x.get("name")): x.get("value") for x in features}
        assert "cross_horizon" in by_name
        assert "msl_meta" in by_name
        assert by_name["cross_horizon"]["suggested_policy"] == "reduce_risk"

    asyncio.run(_run())


def test_http_market_state_provider_from_env(monkeypatch):
    monkeypatch.setenv("AGENT_MARKET_STATE_BASE_URL", "http://localhost:9999")
    monkeypatch.setenv("AGENT_MARKET_STATE_TIMEOUT_S", "3.5")
    p = HttpMarketStateProvider.from_env()
    assert p._base_url == "http://localhost:9999"  # noqa: SLF001
    assert float(p._timeout_s) == 3.5  # noqa: SLF001


def test_http_market_state_provider_marks_msl_contract_missing_fields(monkeypatch):
    payload = {
        "exchange": "binance",
        "symbol": "ETHUSDT",
        "msl": {"version": 2, "timestamp": "2026-03-09T12:00:00Z", "symbol": "ETHUSDT"},
        "msl_meta": {"schema_version": 2, "inference_version": "msl_generator_v2"},
        "state_features": {},
        "anomaly_flags": [],
        "raw_market_structure": {},
    }

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class _Client:
        def __init__(self, *args, **kwargs):  # noqa: ANN003
            _ = (args, kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            _ = (exc_type, exc, tb)
            return False

        async def get(self, url: str):
            _ = url
            return _Resp()

    import agent_server_new.adapters.market_state_http as mod

    monkeypatch.setattr(mod.httpx, "AsyncClient", _Client)

    async def _run():
        provider = HttpMarketStateProvider("http://127.0.0.1:8080")
        snap = await provider.get_market_state("binance", "ETHUSDT")
        assert "msl_contract_missing_required_fields" in set(snap.anomaly_flags)

    asyncio.run(_run())


def test_http_market_state_provider_marks_schema_version_unsupported(monkeypatch):
    payload = {
        "exchange": "binance",
        "symbol": "ETHUSDT",
        "msl": _sample_msl(),
        "msl_meta": {"schema_version": 99, "inference_version": "msl_generator_v99"},
        "state_features": {},
        "anomaly_flags": [],
        "raw_market_structure": {},
    }

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class _Client:
        def __init__(self, *args, **kwargs):  # noqa: ANN003
            _ = (args, kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            _ = (exc_type, exc, tb)
            return False

        async def get(self, url: str):
            _ = url
            return _Resp()

    import agent_server_new.adapters.market_state_http as mod

    monkeypatch.setattr(mod.httpx, "AsyncClient", _Client)

    async def _run():
        provider = HttpMarketStateProvider("http://127.0.0.1:8080")
        snap = await provider.get_market_state("binance", "ETHUSDT")
        assert "msl_meta_schema_version_unsupported" in set(snap.anomaly_flags)

    asyncio.run(_run())
