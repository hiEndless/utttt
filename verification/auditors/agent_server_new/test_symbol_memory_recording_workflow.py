import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
from services.agent_server_new.adapters.symbol_memory_inmemory import InMemorySymbolMemoryAdapter
from services.agent_server_new.app.workflows.trade_event_workflow import TradeEventInput, TradeEventWorkflow
from services.agent_server_new.domain.contracts import Confidence, SignalVerdict
from services.agent_server_new.ports.market_state import MarketStateSnapshot


def _sample_msl() -> dict:
    return {
        "version": 2,
        "timestamp": "2026-03-09T12:00:00Z",
        "symbol": "ETHUSDT",
        "market_regime": {"trend": "bullish", "phase": "continuation", "timeframe_alignment": "aligned", "strength": 0.72},
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
            cross_horizon={"alignment": "aligned", "suggested_policy": "follow_long_term", "policy_reason": "timeframe_aligned"},
            state_features={"evidence": {}, "anomalies": {}},
            anomaly_flags=[
                "state_features_semantic_contract_missing",
                "msl_meta_schema_version_missing",
                "external_event_input_ignored",
            ],
        )


class _Position:
    async def get_position_context(self, exchange: str, symbol: str):
        _ = (exchange, symbol)
        return {"has_position": False}


class _Events:
    async def get_active_events(self, exchange: str, symbol: str):
        _ = (exchange, symbol)
        return []


def test_trade_event_workflow_records_symbol_memory():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="medium", score=0.7)),
        )
        memory = InMemorySymbolMemoryAdapter()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=None,
            recorder=None,
            symbol_memory_provider=memory,
            symbol_memory_recorder=memory,
        )
        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-memory-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        assert out.agent_plan.action == "add"
        mem = await memory.get_symbol_memory("binance", "ETHUSDT", limit=2)
        assert mem["summary"]["event_count"] == 1
        assert mem["summary"]["last_plan_action"] == "add"
        assert mem["summary"]["contract_warning_count"] == 2
        assert "state_features_semantic_contract_missing" in list(mem["summary"]["recent_contract_warning_types"] or [])
        assert mem["recent"][0]["event_id"] == "evt-memory-001"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()
