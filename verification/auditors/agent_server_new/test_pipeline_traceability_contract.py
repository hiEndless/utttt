import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
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
            msl_meta={"schema_version": 2, "inference_version": "msl_generator_v2"},
            cross_horizon={"alignment": "aligned", "suggested_policy": "follow_long_term", "policy_reason": "timeframe_aligned"},
            state_features={"evidence": {}, "anomalies": {}},
        )


class _Position:
    async def get_position_context(self, exchange: str, symbol: str):
        _ = (exchange, symbol)
        return {"has_position": False}


class _Events:
    async def get_active_events(self, exchange: str, symbol: str):
        _ = (exchange, symbol)
        return [
            {"event_id": "sel-1", "source": "event_center_new", "type": "onchain_alert", "direction": "bullish", "score": 0.81}
        ]


class _Recorder:
    def __init__(self) -> None:
        self.outputs = []

    async def record_market_context(self, event_id: str, payload):  # noqa: ANN001
        _ = (event_id, payload)

    async def record_agent_output(self, event_id: str, agent_name: str, payload):  # noqa: ANN001
        self.outputs.append((event_id, agent_name, dict(payload or {})))

    def get_payload(self, event_id: str, agent_name: str) -> dict:
        for row_event_id, row_agent, row_payload in self.outputs:
            if row_event_id == event_id and row_agent == agent_name:
                return dict(row_payload or {})
        return {}


def test_pipeline_traceability_selected_event_to_decision_trace():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.9)),
        )
        recorder = _Recorder()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            recorder=recorder,
        )
        event_id = "evt-trace-001"
        await wf.run(
            TradeEventInput(
                event_id=event_id,
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "onchain_alert", "source": "event_center_new"},
            )
        )

        trace = recorder.get_payload(event_id, "decision_trace")
        assert trace
        routing = dict(trace.get("routing") or {})
        assert routing.get("pipeline_mode") == "minimal"
        assert routing.get("event_type_raw") == "onchain_alert"
        assert routing.get("event_type_normalized") == "onchain_alert"
        assert routing.get("event_type_match_mode") == "canonical_or_raw"
        assert ((trace.get("event") or {}).get("payload") or {}).get("source") == "event_center_new"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()
