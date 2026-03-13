import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
from services.agent_server_new.domain.signal_decision_agent import RoutedRuleBasedSignalDecisionAgent


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


def test_routed_rule_based_signal_decision_agent_routes_and_evaluates():
    agent = RoutedRuleBasedSignalDecisionAgent(
        router_config={
            "default_agent_key": "generic",
            "rules": [{"agent_key": "social_news", "keywords": ["news"]}],
        }
    )
    out = agent.decide(
        signal_direction="long",
        msl=_build_msl_from_dict(_sample_msl()),
        key_market_features={},
        active_events=[],
        signal_event={"event_type": "news_signal"},
        position_context={},
    )
    assert out.decision_agent_key == "social_news"
    assert out.signal.verdict in {"accept", "reject", "uncertain"}
