from __future__ import annotations

import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from contracts.semantic_policies.source_semantics import (
    get_alternative_source_allowed_provider_states,
    get_event_center_empty_provider_state,
    get_event_center_present_provider_state,
)


def test_source_semantics_policy_has_required_structure() -> None:
    path = PROJECT_ROOT / "contracts" / "semantic_policies" / "source_semantics.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    assert isinstance(data.get("version"), int)
    policies = data.get("policies")
    assert isinstance(policies, list) and policies

    item = next((x for x in policies if isinstance(x, dict) and str(x.get("name") or "") == "alternative_sources_summary"), None)
    assert isinstance(item, dict)

    required_keys = {str(x).strip() for x in list(item.get("required_keys") or []) if str(x).strip()}
    assert {
        "available_sources",
        "unavailable_sources",
        "provider_states",
        "data_sources",
        "inference_sources",
        "feature_keys",
        "evidence_counts",
    }.issubset(required_keys)

    default_rules = item.get("default_rules") or {}
    assert isinstance(default_rules, dict)
    for key in (
        "event_center",
        "market_state_feature_fallback",
        "market_state_event_fallback",
        "agent_fusion_fallback",
    ):
        assert key in default_rules

    provider_state_policy = item.get("provider_state_policy") or {}
    assert isinstance(provider_state_policy, dict)
    enums = provider_state_policy.get("enums") or {}
    assert isinstance(enums, dict)
    assert set(enums.keys()) == {"feature", "event_center", "market_state_fusion"}
    for scope in ("feature", "event_center", "market_state_fusion"):
        values = [str(x).strip() for x in list(enums.get(scope) or []) if str(x).strip()]
        assert values
        assert len(values) == len(set(values))

    unavailable_states = [str(x).strip() for x in list(provider_state_policy.get("unavailable_states") or []) if str(x).strip()]
    assert set(unavailable_states) == {"noop", "empty", "unavailable", "none"}


def test_source_semantics_runtime_helper_returns_event_center_states_within_allowed() -> None:
    allowed = get_alternative_source_allowed_provider_states()
    assert get_event_center_present_provider_state() in allowed
    assert get_event_center_empty_provider_state() in allowed
