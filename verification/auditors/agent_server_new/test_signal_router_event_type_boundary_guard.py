import sys
from pathlib import Path

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.domain.signal_router import normalize_signal_event_type, route_signal_agent_key


@pytest.mark.parametrize(
    ("payload", "expected_agent_key"),
    [
        ({"selected_type": "market_indicator_signal"}, "technical"),
        ({"event_type": "ta_signal"}, "technical"),
        ({"event_type": "market_indicator_event_signal"}, "technical"),
        ({"event_type": "whale_transfer_alert"}, "onchain"),
        ({"event_type": "chain_wallet_anomaly"}, "onchain"),
        ({"event_type": "liquidation_spike"}, "liquidation"),
        ({"event_type": "market_large_liquidation"}, "liquidation"),
        ({"event_type": "social_news_signal"}, "social_news"),
        ({"event_type": "social_media_hot_news"}, "social_news"),
    ],
)
def test_event_center_to_agent_event_type_boundary_hits_router_baseline(payload: dict, expected_agent_key: str) -> None:
    key = route_signal_agent_key(signal_event={"payload": dict(payload)})
    assert key == expected_agent_key


@pytest.mark.parametrize(
    ("payload", "expected_matched", "expected_normalized"),
    [
        ({"selected_type": "market_indicator_signal"}, "canonical_or_raw", "market_indicator_signal"),
        ({"event_type": "ta_signal"}, "alias", "market_indicator_signal"),
        ({"event_type": "chain_wallet_anomaly"}, "alias", "onchain_wallet_anomaly"),
        ({"event_type": "market_large_liquidation"}, "alias", "large_liquidation"),
        ({"event_type": "social_news_signal"}, "alias", "social_news"),
        ({"event_type": "social_media_hot_news"}, "alias", "social_news"),
    ],
)
def test_event_type_normalization_diagnosis(payload: dict, expected_matched: str, expected_normalized: str) -> None:
    out = normalize_signal_event_type(signal_event={"payload": dict(payload)})
    assert out["matched"] == expected_matched
    assert out["normalized_event_type"] == expected_normalized
