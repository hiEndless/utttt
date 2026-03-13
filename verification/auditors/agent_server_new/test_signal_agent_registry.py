import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.domain.signal_agent_registry import (  # noqa: E402
    default_signal_decision_prompt_profiles,
    get_signal_agent_spec,
    list_signal_agent_keys,
    resolve_signal_agent_key,
)


def test_signal_agent_registry_contains_business_agent_keys() -> None:
    keys = set(list_signal_agent_keys())
    assert {"technical", "liquidation", "onchain", "social_news", "generic"} <= keys


def test_signal_agent_registry_resolve_unknown_to_generic() -> None:
    assert resolve_signal_agent_key("x_unknown") == "generic"
    assert resolve_signal_agent_key("") == "generic"


def test_signal_agent_registry_spec_lookup() -> None:
    spec = get_signal_agent_spec("onchain")
    assert spec.key == "onchain"
    assert "链上" in spec.description


def test_signal_agent_registry_exposes_default_prompt_profiles() -> None:
    profiles = default_signal_decision_prompt_profiles()
    assert str((profiles.get("technical") or {}).get("focus") or "") == "technical_signal_validation"
    assert str((profiles.get("technical") or {}).get("task") or "")
    assert str((profiles.get("social_news") or {}).get("focus") or "") == "social_news_event_validation"
