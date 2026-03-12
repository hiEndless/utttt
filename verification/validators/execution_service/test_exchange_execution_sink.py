from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.execution_service.adapters.exchange_execution_sink import ExchangeExecutionSink
from services.execution_service.domain.contracts import DecisionIntent


class _FakeBinanceReconcileSink(ExchangeExecutionSink):
    def __init__(
        self,
        *,
        status: str,
        executed_qty: str = "0.25",
        avg_price: str = "",
        price: str = "2000.0",
        quote_qty: str = "0",
    ) -> None:
        super().__init__(venue="binance", dry_run=False, api_key="k", api_secret="s")
        self._status = status
        self._executed_qty = executed_qty
        self._avg_price = avg_price
        self._price = price
        self._quote_qty = quote_qty

    async def _binance_query_order(self, *, symbol: str, order_id: str):  # type: ignore[override]
        return {
            "symbol": symbol,
            "orderId": order_id,
            "status": self._status,
            "executedQty": self._executed_qty,
            "avgPrice": self._avg_price,
            "price": self._price,
            "cummulativeQuoteQty": self._quote_qty,
        }


def test_exchange_sink_submit_dry_run_add_long_builds_buy_market_order() -> None:
    sink = ExchangeExecutionSink(venue="binance", dry_run=True, default_order_qty=0.002)
    decision = DecisionIntent.from_dict(
        {
            "decision_id": "dec-001",
            "exchange": "binance",
            "symbol": "ethusdt",
            "direction_intent": "long",
            "confidence": {"level": "medium", "score": 0.6},
            "decision_confidence": {"level": "medium", "score": 0.6},
            "cross_horizon_policy": {},
            "risk_hints": {},
        }
    )

    out = asyncio.run(sink.submit(decision, "add"))
    assert out["mode"] == "exchange"
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
            "decision_confidence": {"level": "high", "score": 0.8},
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
            "decision_confidence": {"level": "low", "score": 0.2},
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
    assert out["mode"] == "exchange"
    assert out["dry_run"] is True
    assert out["status"] == "submitted"
    assert "dry-run" in str(out.get("note") or "").lower()


def test_exchange_sink_reconcile_maps_binance_filled_to_filled() -> None:
    sink = _FakeBinanceReconcileSink(status="FILLED", avg_price="1999.9")
    out = asyncio.run(
        sink.reconcile(
            "123456",
            {"decision_id": "dec-004", "exchange": "binance", "symbol": "ETHUSDT"},
        )
    )
    assert out["dry_run"] is False
    assert out["status"] == "filled"
    assert out["exchange_status_raw"] == "FILLED"
    assert out["avg_price"] == 1999.9


def test_exchange_sink_reconcile_maps_binance_canceled_to_canceled() -> None:
    sink = _FakeBinanceReconcileSink(status="CANCELED")
    out = asyncio.run(
        sink.reconcile(
            "123457",
            {"decision_id": "dec-005", "exchange": "binance", "symbol": "ETHUSDT"},
        )
    )
    assert out["status"] == "canceled"
    assert out["exchange_status_raw"] == "CANCELED"


def test_exchange_sink_reconcile_unknown_status_fallback_submitted() -> None:
    sink = _FakeBinanceReconcileSink(status="PARTIALLY_FILLED")
    out = asyncio.run(
        sink.reconcile(
            "123458",
            {"decision_id": "dec-006", "exchange": "binance", "symbol": "ETHUSDT"},
        )
    )
    assert out["status"] == "submitted"
    assert out["exchange_status_raw"] == "PARTIALLY_FILLED"


def test_exchange_sink_reconcile_avg_price_fallback_to_quote_div_qty() -> None:
    sink = _FakeBinanceReconcileSink(
        status="PARTIALLY_FILLED",
        executed_qty="0.5",
        avg_price="",
        price="",
        quote_qty="1100",
    )
    out = asyncio.run(
        sink.reconcile(
            "123459",
            {"decision_id": "dec-007", "exchange": "binance", "symbol": "ETHUSDT"},
        )
    )
    assert out["status"] == "submitted"
    assert out["avg_price"] == 2200.0
