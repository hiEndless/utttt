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
