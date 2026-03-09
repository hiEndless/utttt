from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from execution_service.adapters.exchange_execution_sink import ExchangeExecutionSink
from execution_service.domain.contracts import DecisionIntent


def test_exchange_sink_submit_dry_run_add_long_builds_buy_market_order() -> None:
    sink = ExchangeExecutionSink(venue="binance", dry_run=True, default_order_qty=0.002)
    decision = DecisionIntent.from_dict(
        {
            "decision_id": "dec-001",
            "exchange": "binance",
            "symbol": "ethusdt",
            "direction_intent": "long",
            "confidence": {"level": "medium", "score": 0.6},
            "cross_horizon_policy": {},
            "risk_hints": {},
        }
    )

    out = asyncio.run(sink.submit(decision, "add"))
    assert out["mode"] == "exchange_skeleton"
    assert out["dry_run"] is True
    assert out["status"] == "submitted"
    assert out["symbol"] == "ETHUSDT"
    assert out["request"]["side"] == "BUY"
    assert out["request"]["type"] == "MARKET"
    assert out["request"]["quantity"] == "0.002000"


def test_exchange_sink_submit_dry_run_reduce_uses_position_side() -> None:
    sink = ExchangeExecutionSink(venue="binance", dry_run=True, default_order_qty=0.001)
    decision = DecisionIntent.from_dict(
        {
            "decision_id": "dec-002",
            "exchange": "binance",
            "symbol": "ETHUSDT",
            "direction_intent": "long",
            "confidence": {"level": "high", "score": 0.8},
            "cross_horizon_policy": {},
            "risk_hints": {"position_side": "short", "order_qty": 0.01},
        }
    )

    out = asyncio.run(sink.submit(decision, "reduce"))
    assert out["request"]["side"] == "BUY"
    assert out["request"]["quantity"] == "0.010000"


def test_exchange_sink_submit_add_none_direction_raises() -> None:
    sink = ExchangeExecutionSink(venue="binance", dry_run=True, default_order_qty=0.001)
    decision = DecisionIntent.from_dict(
        {
            "decision_id": "dec-003",
            "exchange": "binance",
            "symbol": "ETHUSDT",
            "direction_intent": "none",
            "confidence": {"level": "low", "score": 0.2},
            "cross_horizon_policy": {},
            "risk_hints": {},
        }
    )

    with pytest.raises(ValueError, match="direction_intent"):
        asyncio.run(sink.submit(decision, "add"))


def test_exchange_sink_reconcile_dry_run_placeholder() -> None:
    sink = ExchangeExecutionSink(venue="binance", dry_run=True, default_order_qty=0.001)
    out = asyncio.run(
        sink.reconcile(
            "binance-ord-001",
            {
                "decision_id": "dec-001",
                "exchange": "binance",
                "symbol": "ethusdt",
            },
        )
    )
    assert out["mode"] == "exchange_skeleton"
    assert out["dry_run"] is True
    assert out["status"] == "submitted"
    assert "dry-run" in str(out.get("note") or "").lower()
