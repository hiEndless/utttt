import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.domain.signal_router import (
    reset_signal_router_cache,
    route_signal_agent_key,
)


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


def test_signal_router_supports_custom_config(tmp_path) -> None:  # noqa: ANN001
    custom = tmp_path / "router.json"
    custom.write_text(
        json.dumps(
            {
                "default_agent_key": "generic",
                "rules": [
                    {"agent_key": "wallet_watch", "keywords": ["wallet", "whale_alert"]},
                    {"agent_key": "technical", "keywords": ["indicator"]},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    key = route_signal_agent_key(
        signal_event={"payload": {"event_type": "wallet_alert"}},
        router_config=json.loads(custom.read_text(encoding="utf-8")),
    )
    assert key == "wallet_watch"


def test_signal_router_loads_config_from_env(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    custom = tmp_path / "router_env.json"
    custom.write_text(
        json.dumps(
            {
                "default_agent_key": "generic",
                "rules": [
                    {"agent_key": "macro_watch", "keywords": ["macro", "news"]},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_SIGNAL_ROUTER_CONFIG_FILE", str(custom))
    reset_signal_router_cache()
    key = route_signal_agent_key(signal_event={"payload": {"event_type": "macro_news"}})
    assert key == "macro_watch"
