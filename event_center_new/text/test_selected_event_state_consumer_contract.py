from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.market_state_engine.src.service import MarketStateService


def _load_selected_schema() -> dict:
    path = Path(PROJECT_ROOT) / "event_center_new" / "docs" / "selected_event.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_selected_event_schema_keeps_market_state_consumer_core_fields() -> None:
    schema = _load_selected_schema()
    required = set(schema.get("required") or [])
    # 中文注释：冻结状态层 evidence 聚合依赖字段，防止 selected_event 漂移影响 state 侧摘要。
    assert {"asset", "selected_type", "direction_hint", "priority", "trace"} <= required


def test_selected_event_can_build_market_state_evidence_summary() -> None:
    selected_items = [
        {
            "asset": "binance:ETHUSDT",
            "ts_ms": 1710000000000,
            "selected_type": "breakout_signal",
            "direction_hint": "bullish",
            "priority": "high",
            "context_snapshot": {"k": "v"},
            "trace": {"schema_version": "selected-v2"},
            "route": {"horizon": "5m"},
        },
        {
            "asset": "binance:ETHUSDT",
            "ts_ms": 1710000001000,
            "selected_type": "onchain_alert",
            "direction_hint": "mixed",
            "priority": "medium",
            "context_snapshot": {"k2": "v2"},
            "trace": {"schema_version": "selected-v2"},
            "route": {"horizon": "15m"},
        },
    ]
    summary = MarketStateService._build_selected_event_evidence(selected_items)  # noqa: SLF001
    assert summary["selected_events_count"] == 2
    assert summary["selected_event_types"] == ["breakout_signal", "onchain_alert"]
    assert summary["selected_event_directions"] == ["bullish", "mixed"]
    assert summary["selected_event_priorities"] == ["high", "medium"]
    assert summary["selected_event_assets"] == ["binance:ETHUSDT"]
