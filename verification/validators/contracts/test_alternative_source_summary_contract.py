from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from contracts.schemas.alternative_source_summary_contract import (
    get_alternative_source_names,
    get_alternative_source_provider_states_from_schema,
    get_alternative_source_required_keys,
)
from contracts.semantic_policies.source_semantics import get_alternative_source_allowed_provider_states


def test_alternative_source_contract_required_keys_stable() -> None:
    required = set(get_alternative_source_required_keys())
    assert {
        "available_sources",
        "unavailable_sources",
        "provider_states",
        "data_sources",
        "inference_sources",
        "feature_keys",
        "evidence_counts",
    }.issubset(required)


def test_alternative_source_contract_source_names_stable() -> None:
    assert tuple(get_alternative_source_names()) == ("news", "social", "onchain")


def test_alternative_source_contract_provider_states_cover_policy_allowed_values() -> None:
    schema_states = get_alternative_source_provider_states_from_schema()
    policy_states = get_alternative_source_allowed_provider_states()
    assert policy_states <= schema_states

