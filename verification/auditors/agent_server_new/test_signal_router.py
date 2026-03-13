import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.domain.signal_router import (
    reset_signal_router_cache,
    route_signal_agent_key,
    validate_signal_router_config,
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


def test_signal_router_prefers_event_type_route_over_keywords() -> None:
    key = route_signal_agent_key(
        signal_event={"payload": {"event_type": "onchain_wallet_anomaly", "source_category": "social"}}
    )
    assert key == "onchain"


def test_signal_router_routes_by_source_category_when_event_type_unknown() -> None:
    key = route_signal_agent_key(
        signal_event={"payload": {"event_type": "custom_unknown_type", "source_category": "liquidation"}}
    )
    assert key == "liquidation"


def test_signal_router_routes_by_event_source_category_alias() -> None:
    key = route_signal_agent_key(
        signal_event={"payload": {"type": "custom_unknown_type", "event_source_category": "social"}}
    )
    assert key == "social_news"


def test_signal_router_supports_custom_config(tmp_path) -> None:  # noqa: ANN001
    custom = tmp_path / "router.json"
    custom.write_text(
        json.dumps(
            {
                "default_agent_key": "generic",
                "event_type_routes": {"wallet_alert": "wallet_watch"},
                "source_category_routes": {"onchain": "wallet_watch"},
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


def test_signal_router_validate_rejects_duplicate_keywords() -> None:
    cfg = {
        "default_agent_key": "generic",
        "rules": [
            {"agent_key": "technical", "keywords": ["indicator"]},
            {"agent_key": "onchain", "keywords": ["indicator"]},
        ],
    }
    try:
        validate_signal_router_config(cfg)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "关键词重复冲突" in str(exc)


def test_signal_router_validate_rejects_unknown_agent_key() -> None:
    cfg = {
        "default_agent_key": "generic",
        "rules": [
            {"agent_key": "custom_unknown", "keywords": ["alpha"]},
        ],
    }
    try:
        validate_signal_router_config(
            cfg,
            allowed_agent_keys={"technical", "liquidation", "onchain", "social_news", "generic"},
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "agent_key 非法" in str(exc)


def test_signal_router_validate_rejects_unknown_agent_key_in_event_type_routes() -> None:
    cfg = {
        "default_agent_key": "generic",
        "event_type_routes": {"macro_news": "custom_unknown"},
        "rules": [
            {"agent_key": "social_news", "keywords": ["news"]},
        ],
    }
    try:
        validate_signal_router_config(
            cfg,
            allowed_agent_keys={"technical", "liquidation", "onchain", "social_news", "generic"},
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "event_type_routes[macro_news] 非法" in str(exc)


def test_signal_router_validate_rejects_empty_rules() -> None:
    cfg = {"default_agent_key": "generic", "rules": []}
    try:
        validate_signal_router_config(cfg)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "rules 必须是非空数组" in str(exc)
