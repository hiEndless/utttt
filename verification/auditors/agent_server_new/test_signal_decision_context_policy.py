import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.domain.signal_decision_context_policy import (
    build_llm_observation_context,
    clip_active_events_for_agent,
    clip_key_market_features_for_agent,
)


def test_clip_active_events_for_onchain_prefers_onchain_events() -> None:
    events = [
        {"type": "social_trending", "score": 0.9},
        {"type": "wallet_alert", "score": 0.7, "evidence": {"event_source_category": "onchain"}},
        {"type": "exchange_flow_spike", "score": 0.6, "source": "onchain_provider"},
        {"type": "macro_news", "score": 0.8},
    ]
    out = clip_active_events_for_agent(decision_agent_key="onchain", active_events=events, max_items=2)
    assert len(out) == 2
    assert str(out[0].get("type") or "") in {"wallet_alert", "exchange_flow_spike"}


def test_clip_key_market_features_for_social_news_prefers_news_related_features() -> None:
    key_features = {
        "profile": "macro_sentiment",
        "features": [
            {"name": "cross_horizon", "value": {}},
            {"name": "alternative_source_summary", "value": {}},
            {"name": "oi_velocity", "value": "up"},
            {"name": "social_sentiment_score", "value": 0.8},
        ],
        "contract_warnings": ["x"],
    }
    out = clip_key_market_features_for_agent(
        decision_agent_key="social_news",
        key_market_features=key_features,
        max_items=3,
    )
    names = [str((x or {}).get("name") or "") for x in list(out.get("features") or [])]
    assert "cross_horizon" in names
    assert "alternative_source_summary" in names
    assert "social_sentiment_score" in names
    assert out.get("contract_warnings") == ["x"]


def test_build_llm_observation_context_normalizes_unknown_agent_key() -> None:
    out = build_llm_observation_context(
        decision_agent_key="unknown",
        key_market_features={"features": [{"name": "cross_horizon", "value": {}}]},
        active_events=[{"type": "custom_event", "score": 0.2}],
        features_limit=2,
        events_limit=1,
    )
    assert out.get("decision_agent_key") == "generic"
    prompt = dict(out.get("decision_prompt") or {})
    assert prompt.get("focus") == "generic_signal_validation"
    assert len(list(out.get("active_events") or [])) == 1
