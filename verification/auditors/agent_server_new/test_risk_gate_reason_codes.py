from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
from services.agent_server_new.app.workflows.trade_event_workflow import _derive_risk_gate_context
from services.agent_server_new.domain.risk_gate_reasons import (
    RISK_GATE_REASON_CODES,
    risk_gate_reason_active_event,
    risk_gate_reason_portfolio_risk_state,
)


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


def test_risk_gate_reason_registry_unique() -> None:
    assert len(RISK_GATE_REASON_CODES) == len(set(RISK_GATE_REASON_CODES))


def test_risk_gate_reason_helpers_are_canonical() -> None:
    assert risk_gate_reason_portfolio_risk_state("warn") in set(RISK_GATE_REASON_CODES)
    assert risk_gate_reason_active_event("forced_liquidation", "critical") in set(RISK_GATE_REASON_CODES)


def test_derived_risk_gate_reasons_within_canonical_set() -> None:
    msl = _build_msl_from_dict(_sample_msl())
    _, reasons = _derive_risk_gate_context(
        msl=msl,
        position_context={
            "current_position": {"cooldown_seconds_left": 30},
            "portfolio_risk": {"risk_state": "frozen"},
        },
        active_events=[{"type": "forced_liquidation", "score": 0.91}],
    )
    assert set(reasons).issubset(set(RISK_GATE_REASON_CODES))

