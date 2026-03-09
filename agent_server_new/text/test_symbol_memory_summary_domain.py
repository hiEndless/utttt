import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent_server_new.domain.symbol_memory_summary import build_symbol_memory_summary


def test_build_symbol_memory_summary_counts_and_bias():
    raw = [
        {"ts": 1000, "event_id": "e1", "signal": {"direction": "long", "verdict": "accept"}, "plan": {"action": "add", "direction": "long"}},
        {"ts": 1100, "event_id": "e2", "signal": {"direction": "long", "verdict": "accept"}, "plan": {"action": "add", "direction": "long"}},
        {"ts": 1200, "event_id": "e3", "signal": {"direction": "short", "verdict": "reject"}, "plan": {"action": "hold", "direction": "none"}},
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
