import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
from services.agent_server_new.app.context_builder import ContextBuilder
from services.agent_server_new.ports.market_state import MarketStateSnapshot


def _sample_msl() -> dict:
    return {
        "version": 2,
        "timestamp": "2026-03-09T12:00:00Z",
        "symbol": "ETHUSDT",
        "market_regime": {"trend": "bullish", "phase": "continuation", "timeframe_alignment": "aligned", "strength": 0.7},
        "liquidity_state": {"dominant_pressure": "buyers", "liquidity_risk": "neutral", "orderbook_bias": "neutral", "liquidation_proximity": "none"},
        "positioning_state": {"crowding": "balanced", "whale_bias": "unknown", "retail_bias": "unknown", "oi_trend": "expanding"},
        "volatility_state": {"volatility_regime": "normal", "expansion_risk": "unknown", "volatility_direction": "upside"},
        "market_risk_state": {"cascade_risk": "low", "squeeze_probability": "low", "reversal_risk": "low"},
        "market_structure_state": {"support_strength": "unknown", "resistance_strength": "unknown", "range_state": "breakout", "trend_structure": "hh_hl"},
        "key_levels": {"major_support": [], "major_resistance": [], "liquidation_clusters": []},
        "anomalies": [],
        "summary": "ok",
    }


class _MarketState:
    async def get_market_state(self, exchange: str, symbol: str):
        _ = (exchange, symbol)
        return MarketStateSnapshot(
            exchange="binance",
            symbol="ETHUSDT",
            msl=_build_msl_from_dict(_sample_msl()),
            msl_meta={"schema_version": 2},
            cross_horizon={"suggested_policy": "wait_confirmation"},
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


class _Memory:
    def __init__(self) -> None:
        now = int(time.time() * 1000)
        self._payload = {
            "summary": {"event_count": 999},
            "recent": [
                {"event_id": "evt-old", "ts": now - 20_000, "plan": {"action": "hold"}},
                {"event_id": "evt-dup", "ts": now - 2_000, "plan": {"action": "hold"}},
                {"event_id": "evt-dup", "ts": now - 1_000, "plan": {"action": "add"}},
                {"event_id": "evt-new", "ts": now - 500, "plan": {"action": "add"}},
            ],
        }

    async def get_symbol_memory(self, exchange: str, symbol: str, limit: int = 20):  # noqa: ARG002
        _ = (exchange, symbol, limit)
        return dict(self._payload)


def test_context_builder_applies_ttl_dedup_topk_for_recent_memory():
    async def _run():
        builder = ContextBuilder(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            symbol_memory_provider=_Memory(),
            memory_recent_topk=2,
            memory_recent_ttl_ms=5_000,
            memory_dedup_key="event_id",
            max_key_features=10,
        )
        built = await builder.build(
            event_id="evt-now",
            exchange="binance",
            symbol="ETHUSDT",
            signal_payload={"event_type": "indicator_signal"},
        )
        features = list((built.ctx.key_market_features or {}).get("features") or [])
        by_name = {str(item.get("name")): item.get("value") for item in features}
        recent = list(by_name.get("recent_memory") or [])
        obs = dict((built.ctx.key_market_features or {}).get("memory_observability") or {})
        assert len(recent) == 2
        assert recent[0]["event_id"] == "evt-dup"
        assert recent[0]["plan"]["action"] == "add"
        assert recent[1]["event_id"] == "evt-new"
        assert obs["memory_hit"] is True
        assert obs["memory_raw_recent_count"] == 4
        assert obs["memory_filtered_recent_count"] == 2
        assert obs["memory_dropped_count"] == 2

    asyncio.run(_run())
