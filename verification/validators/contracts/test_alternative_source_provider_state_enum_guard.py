from __future__ import annotations

import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.agent_server_new.app.context_builder import _extract_alternative_source_summary
from services.event_center_new.ec.context.builder import _build_alternative_sources_summary
from services.event_center_new.ec.contracts import Evidence
from services.market_state_engine.src.service import _build_alternative_sources_fusion


def _allowed_provider_states() -> set[str]:
    path = PROJECT_ROOT / "contracts" / "semantic_policies" / "source_semantics.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    item = next(
        (
            x
            for x in list(data.get("policies") or [])
            if isinstance(x, dict) and str(x.get("name") or "") == "alternative_sources_summary"
        ),
        {},
    )
    policy = dict((item or {}).get("provider_state_policy") or {})
    enums = dict(policy.get("enums") or {})
    out: set[str] = set()
    for scope in ("feature", "event_center", "market_state_fusion"):
        out.update([str(x).strip() for x in list(enums.get(scope) or []) if str(x).strip()])
    return out


def test_event_center_provider_states_within_policy_enum() -> None:
    allowed = _allowed_provider_states()
    summary = _build_alternative_sources_summary(
        [
            Evidence(
                ts_ms=1710000000000,
                type="news.macro",
                direction="mixed",
                strength=0.4,
                horizon="mid",
                ttl_ms=600000,
                importance=0.7,
                attrs={"source_type": "news", "source_name": "coindesk"},
            ),
            Evidence(
                ts_ms=1710000000001,
                type="onchain.alert",
                direction="bearish",
                strength=0.6,
                horizon="short",
                ttl_ms=600000,
                importance=0.9,
                attrs={"source_type": "onchain", "source_name": "whale_monitor"},
            ),
        ]
    )
    states = {str(v).strip() for v in dict(summary.get("provider_states") or {}).values() if str(v).strip()}
    assert states
    assert states <= allowed


def test_market_state_fusion_provider_states_within_policy_enum() -> None:
    allowed = _allowed_provider_states()
    fusion = _build_alternative_sources_fusion(
        feature_alt={
            "news": {"available": True, "provider_state": "primary", "features": {"headline_score": 0.8}},
            "social": {"available": False, "provider_state": "noop", "features": {}},
            "onchain": {"available": False, "provider_state": "empty", "features": {}},
        },
        event_alt_summary={
            "provider_states": {"news": "event_evidence_present", "social": "empty", "onchain": "event_evidence_present"},
            "data_sources": {"news": "event_center_new.news", "social": "event_center_new.social", "onchain": "event_center_new.onchain"},
            "inference_sources": {
                "news": "event_center_new.selector",
                "social": "event_center_new.selector",
                "onchain": "event_center_new.selector",
            },
            "feature_keys": {"news": ["headline_score"], "social": [], "onchain": ["inflow_usd"]},
            "evidence_counts": {"news": 1, "social": 0, "onchain": 2},
        },
    )
    by_source = dict(dict(fusion.get("merged") or {}).get("by_source") or {})
    states = {str(dict(v or {}).get("provider_state") or "").strip() for v in by_source.values()}
    states.discard("")
    assert states
    assert states <= allowed


def test_agent_summary_provider_states_within_policy_enum() -> None:
    allowed = _allowed_provider_states()
    summary = _extract_alternative_source_summary(
        {
            "alternative_sources_fusion": {
                "preferred_source": "feature",
                "conflicts": [],
                "merged": {
                    "available_sources": ["news"],
                    "unavailable_sources": ["social", "onchain"],
                    "by_source": {
                        "news": {
                            "provider_state": "primary",
                            "data_source": "feature_service.news",
                            "inference_source": "feature_service.normalizer",
                            "feature_keys": ["headline_score"],
                        },
                        "social": {"provider_state": "empty", "feature_keys": []},
                        "onchain": {"provider_state": "event_evidence_present", "feature_keys": ["inflow_usd"]},
                    },
                },
            }
        }
    )
    states = {str(v).strip() for v in dict(summary.get("provider_states") or {}).values() if str(v).strip()}
    assert states
    assert states <= allowed
