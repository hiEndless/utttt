import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.domain.symbol_memory_summary import build_symbol_memory_summary


def test_build_symbol_memory_summary_counts_and_bias():
    raw = [
        {"ts": 1000, "event_id": "e1", "signal": {"direction": "long", "verdict": "accept"}, "plan": {"action": "add", "direction": "long"}},
        {"ts": 1100, "event_id": "e2", "signal": {"direction": "long", "verdict": "accept"}, "plan": {"action": "add", "direction": "long"}},
        {"ts": 1200, "event_id": "e3", "signal": {"direction": "short", "verdict": "reject"}, "plan": {"action": "hold", "direction": "neutral"}},
    ]
    out = build_symbol_memory_summary(
        exchange="binance",
        symbol="ethusdt",
        raw_records=raw,
        window=50,
        now_ms=1300,
    )
    assert out["exchange"] == "binance"
    assert out["symbol"] == "ETHUSDT"
    assert out["event_count"] == 3
    assert out["trend_bias"] == "bullish"
    assert out["signal_direction_count"]["long"] == 2
    assert out["signal_direction_count"]["short"] == 1
    assert out["plan_action_count"]["add"] == 2
    assert out["last_event_id"] == "e3"


def test_build_symbol_memory_summary_contract_warnings_aggregate():
    raw = [
        {
            "ts": 1000,
            "event_id": "e1",
            "signal": {"direction": "long", "verdict": "accept"},
            "plan": {"action": "add", "direction": "long"},
            "contract_warnings": ["state_features_semantic_contract_missing"],
        },
        {
            "ts": 1100,
            "event_id": "e2",
            "signal": {"direction": "short", "verdict": "reject"},
            "plan": {"action": "hold", "direction": "neutral"},
            "contract_warnings": ["msl_meta_schema_version_missing", "state_features_semantic_contract_missing"],
        },
        {
            "ts": 1200,
            "event_id": "e3",
            "signal": {"direction": "short", "verdict": "accept"},
            "plan": {"action": "reduce", "direction": "short"},
            "contract_warnings": [],
        },
    ]
    out = build_symbol_memory_summary(
        exchange="binance",
        symbol="ethusdt",
        raw_records=raw,
        window=50,
        now_ms=1300,
    )
    assert out["contract_warning_count"] == 3
    assert out["contract_warning_event_count"] == 2
    assert out["contract_warning_type_count"]["state_features_semantic_contract_missing"] == 2
    assert out["contract_warning_type_count"]["msl_meta_schema_version_missing"] == 1
    assert out["recent_contract_warning_types"][0] == "msl_meta_schema_version_missing"
