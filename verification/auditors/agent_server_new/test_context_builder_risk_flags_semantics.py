from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.app.context_builder import _signal_context_builder


def test_signal_context_builder_normalizes_oi_risk_flags_from_map() -> None:
    out = _signal_context_builder(
        features={
            "open_interest": {
                "risk_flags": {
                    "possible_liquidation_or_unwind": True,
                    "fragile_leverage_build": 1,
                    "ignore_noise": "false",
                }
            }
        },
        signal_event={"payload": {"event_type": "indicator_signal"}},
        active_events=[],
        max_features=20,
    )
    items = list(out.get("features") or [])
    oi_item = next((x for x in items if (x or {}).get("name") == "oi_risk_flags"), {})
    assert oi_item
    assert oi_item["value"] == ["fragile_leverage_build", "possible_liquidation_or_unwind"]


def test_signal_context_builder_includes_alternative_source_summary() -> None:
    out = _signal_context_builder(
        features={
            "evidence": {
                "alternative_sources": {
                    "news": {"available": True, "provider_state": "primary", "features": {"headline_score": 0.8}},
                    "social": {"available": False, "provider_state": "noop", "features": {}},
                    "onchain": {"available": False, "provider_state": "empty", "features": {}},
                }
            }
        },
        signal_event={"payload": {"event_type": "macro_news"}},
        active_events=[],
        max_features=20,
    )
    items = list(out.get("features") or [])
    summary = next((x for x in items if (x or {}).get("name") == "alternative_source_summary"), {})
    assert summary
    value = dict(summary.get("value") or {})
    assert "news" in list(value.get("available_sources") or [])
    assert value.get("provider_states", {}).get("social") == "noop"
    assert value.get("data_sources", {}).get("news") == "feature_service.news"
    assert value.get("inference_sources", {}).get("news") == "feature_service.normalizer"


def test_signal_context_builder_treats_noop_empty_source_as_unavailable() -> None:
    out = _signal_context_builder(
        features={
            "evidence": {
                "alternative_sources": {
                    "news": {"available": True, "provider_state": "noop", "features": {}},
                    "social": {"available": False, "provider_state": "empty", "features": {}},
                    "onchain": {"available": False, "provider_state": "event_evidence_present", "features": {"inflow_usd": 10}},
                }
            }
        },
        signal_event={"payload": {"event_type": "macro_news"}},
        active_events=[],
        max_features=20,
    )
    items = list(out.get("features") or [])
    summary = next((x for x in items if (x or {}).get("name") == "alternative_source_summary"), {})
    assert summary
    value = dict(summary.get("value") or {})
    assert "news" not in list(value.get("available_sources") or [])
    assert "news" in list(value.get("unavailable_sources") or [])
    assert "onchain" in list(value.get("available_sources") or [])


def test_signal_context_builder_prefers_fusion_alternative_source_summary() -> None:
    out = _signal_context_builder(
        features={
            "evidence": {
                "alternative_sources": {
                    "news": {"available": True, "provider_state": "primary", "features": {"headline_score": 0.8}},
                },
                "alternative_sources_fusion": {
                    "preferred_source": "feature",
                    "conflicts": [{"source": "news", "feature_state": "primary", "event_state": "event_evidence_present"}],
                    "merged": {
                        "available_sources": ["news", "onchain"],
                        "unavailable_sources": ["social"],
                        "by_source": {
                            "news": {
                                "provider_state": "primary",
                                "data_source": "feature_service.news",
                                "inference_source": "feature_service.normalizer",
                                "feature_keys": ["headline_score"],
                            },
                            "social": {
                                "provider_state": "empty",
                                "data_source": "event_center_new.social",
                                "inference_source": "event_center_new.selector",
                                "feature_keys": [],
                            },
                            "onchain": {
                                "provider_state": "event_evidence_present",
                                "data_source": "event_center_new.onchain",
                                "inference_source": "event_center_new.selector",
                                "feature_keys": ["inflow_usd"],
                            },
                        },
                    },
                },
            }
        },
        signal_event={"payload": {"event_type": "macro_news"}},
        active_events=[],
        max_features=20,
    )
    items = list(out.get("features") or [])
    summary = next((x for x in items if (x or {}).get("name") == "alternative_source_summary"), {})
    assert summary
    value = dict(summary.get("value") or {})
    assert value.get("preferred_source") == "feature"
    assert value.get("conflict_count") == 1
    assert "onchain" in list(value.get("available_sources") or [])
    assert value.get("data_sources", {}).get("onchain") == "event_center_new.onchain"
    assert value.get("inference_sources", {}).get("news") == "feature_service.normalizer"


def test_signal_context_builder_fusion_summary_fills_default_source_semantics_when_missing() -> None:
    out = _signal_context_builder(
        features={
            "evidence": {
                "alternative_sources_fusion": {
                    "preferred_source": "event_center",
                    "conflicts": [],
                    "merged": {
                        "available_sources": ["onchain"],
                        "unavailable_sources": ["news", "social"],
                        "by_source": {
                            "news": {"provider_state": "primary", "feature_keys": ["headline_score"]},
                            "social": {"provider_state": "empty", "feature_keys": []},
                            "onchain": {"provider_state": "event_evidence_present", "feature_keys": ["inflow_usd"]},
                        },
                    },
                },
            }
        },
        signal_event={"payload": {"event_type": "macro_news"}},
        active_events=[],
        max_features=20,
    )
    items = list(out.get("features") or [])
    summary = next((x for x in items if (x or {}).get("name") == "alternative_source_summary"), {})
    assert summary
    value = dict(summary.get("value") or {})
    assert value.get("data_sources", {}).get("onchain") == "event_center_new.onchain"
    assert value.get("inference_sources", {}).get("onchain") == "event_center_new.selector"
    assert value.get("data_sources", {}).get("news") == "feature_service.news"
    assert value.get("inference_sources", {}).get("news") == "feature_service.normalizer"
