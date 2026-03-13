import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.domain.signal_router import route_signal_agent_key


def test_signal_router_routes_technical() -> None:
    key = route_signal_agent_key(signal_event={"payload": {"event_type": "indicator_signal"}})
    assert key == "technical"


def test_signal_router_routes_liquidation() -> None:
    key = route_signal_agent_key(signal_event={"payload": {"event_type": "forced_liquidation_cluster"}})
    assert key == "liquidation"


def test_signal_router_routes_onchain() -> None:
    key = route_signal_agent_key(signal_event={"payload": {"event_type": "wallet_alert", "source_category": "onchain"}})
    assert key == "onchain"


def test_signal_router_routes_social_news() -> None:
    key = route_signal_agent_key(signal_event={"payload": {"event_type": "macro_news"}})
    assert key == "social_news"


def test_signal_router_routes_generic_when_unknown() -> None:
    key = route_signal_agent_key(signal_event={"payload": {"event_type": "custom_unknown_type"}})
    assert key == "generic"

