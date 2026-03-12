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
        "risk_state": {"cascade_risk": "low", "squeeze_probability": "low", "reversal_risk": "low"},
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
    async def get_symbol_memory(self, exchange: str, symbol: str, limit: int = 20):  # noqa: ARG002
        _ = (exchange, symbol, limit)
        now = int(time.time() * 1000)
        return {
            "summary": {"event_count": 12, "last_plan_action": "hold"},
            "recent": [{"event_id": "evt-100", "ts": now, "plan": {"action": "add"}}],
        }


def test_context_builder_injects_symbol_memory_features():
    async def _run():
        builder = ContextBuilder(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            symbol_memory_provider=_Memory(),
            max_key_features=8,
        )
        built = await builder.build(
            event_id="evt-101",
            exchange="binance",
            symbol="ETHUSDT",
            signal_payload={"event_type": "indicator_signal"},
        )
        features = list((built.ctx.key_market_features or {}).get("features") or [])
        by_name = {str(item.get("name")): item.get("value") for item in features}
        assert "memory_summary" in by_name
        assert "recent_memory" in by_name
        assert by_name["memory_summary"]["event_count"] == 12
        assert by_name["recent_memory"][0]["event_id"] == "evt-100"

    asyncio.run(_run())
