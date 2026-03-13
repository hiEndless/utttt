import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
from services.agent_server_new.domain.signal_decision_agent import (
    RoutedHybridSignalDecisionAgent,
    RoutedRuleBasedSignalDecisionAgent,
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
    assert out.decision_mode == "rule"
    assert out.llm_parse_status == "rule_only"
    assert out.signal.verdict in {"accept", "reject", "uncertain"}


def test_routed_hybrid_signal_decision_agent_uses_llm_when_valid():
    agent = RoutedHybridSignalDecisionAgent(
        router_config={
            "default_agent_key": "generic",
            "rules": [{"agent_key": "onchain", "keywords": ["onchain"]}],
        }
    )
    out = agent.decide(
        signal_direction="short",
        msl=_build_msl_from_dict(_sample_msl()),
        key_market_features={},
        active_events=[],
        signal_event={"event_type": "onchain_wallet_alert"},
        position_context={},
        llm_result={
            "status": "ok",
            "raw_content": "{\"signal_verdict\":\"accept\",\"signal_direction\":\"short\",\"confidence_score\":0.81,\"reasons\":[\"wallet_flow\"]}",
        },
    )
    assert out.decision_agent_key == "onchain"
    assert out.decision_mode == "llm"
    assert out.llm_parse_status == "llm_ok"
    assert out.signal.direction == "short"
    assert out.signal.verdict == "accept"


def test_routed_hybrid_signal_decision_agent_fallbacks_to_rule_when_llm_invalid():
    agent = RoutedHybridSignalDecisionAgent(
        router_config={
            "default_agent_key": "generic",
            "rules": [{"agent_key": "onchain", "keywords": ["onchain"]}],
        }
    )
    out = agent.decide(
        signal_direction="long",
        msl=_build_msl_from_dict(_sample_msl()),
        key_market_features={},
        active_events=[],
        signal_event={"event_type": "onchain_wallet_alert"},
        position_context={},
        llm_result={"status": "ok", "raw_content": "{\"foo\":\"bar\"}"},
    )
    assert out.decision_agent_key == "onchain"
    assert out.decision_mode == "rule_fallback"
    assert out.llm_parse_status == "llm_invalid_payload"
    assert out.signal.verdict in {"accept", "reject", "uncertain"}


def test_routed_hybrid_signal_decision_agent_rejects_out_of_range_score():
    agent = RoutedHybridSignalDecisionAgent(
        router_config={
            "default_agent_key": "generic",
            "rules": [{"agent_key": "onchain", "keywords": ["onchain"]}],
        }
    )
    out = agent.decide(
        signal_direction="long",
        msl=_build_msl_from_dict(_sample_msl()),
        key_market_features={},
        active_events=[],
        signal_event={"event_type": "onchain_wallet_alert"},
        position_context={},
        llm_result={
            "status": "ok",
            "raw_content": "{\"signal_verdict\":\"accept\",\"signal_direction\":\"long\",\"confidence_score\":1.2,\"reasons\":[]}",
        },
    )
    assert out.decision_mode == "rule_fallback"
    assert out.llm_parse_status == "llm_invalid_payload"


def test_routed_hybrid_signal_decision_agent_rejects_unknown_fields():
    agent = RoutedHybridSignalDecisionAgent(
        router_config={
            "default_agent_key": "generic",
            "rules": [{"agent_key": "onchain", "keywords": ["onchain"]}],
        }
    )
    out = agent.decide(
        signal_direction="long",
        msl=_build_msl_from_dict(_sample_msl()),
        key_market_features={},
        active_events=[],
        signal_event={"event_type": "onchain_wallet_alert"},
        position_context={},
        llm_result={
            "status": "ok",
            "raw_content": "{\"signal_verdict\":\"accept\",\"signal_direction\":\"long\",\"confidence_score\":0.8,\"reasons\":[],\"foo\":\"bar\"}",
        },
    )
    assert out.decision_mode == "rule_fallback"
    assert out.llm_parse_status == "llm_invalid_payload"
