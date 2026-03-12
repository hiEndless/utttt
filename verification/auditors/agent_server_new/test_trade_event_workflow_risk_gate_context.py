import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
from services.agent_server_new.app.workflows.trade_event_workflow import _derive_risk_gate_context


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


def test_derive_risk_gate_context_uses_position_risk_state_and_cooldown() -> None:
    msl = _build_msl_from_dict(_sample_msl())
    ctx = _derive_risk_gate_context(
        msl=msl,
        position_context={
            "current_position": {"cooldown_seconds_left": 30},
            "portfolio_risk": {"risk_state": "frozen"},
        },
        active_events=[],
    )
    assert ctx.global_regime == "critical"
    assert ctx.cooldown_active is True


def test_derive_risk_gate_context_uses_msl_fragility() -> None:
    payload = _sample_msl()
    payload["market_risk_state"] = {"cascade_risk": "medium", "squeeze_probability": "low", "reversal_risk": "low"}
    msl = _build_msl_from_dict(payload)
    ctx = _derive_risk_gate_context(msl=msl, position_context={}, active_events=[])
    assert ctx.global_regime == "elevated"
    assert ctx.cooldown_active is False


def test_derive_risk_gate_context_uses_active_event_pressure() -> None:
    msl = _build_msl_from_dict(_sample_msl())
    ctx = _derive_risk_gate_context(
        msl=msl,
        position_context={},
        active_events=[{"type": "forced_liquidation", "score": 0.91}],
    )
    assert ctx.global_regime == "critical"
