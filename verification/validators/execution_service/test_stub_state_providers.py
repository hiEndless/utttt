from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio

from services.execution_service.adapters.stub_state_providers import (
    StubAccountStateProvider,
    StubPositionStateProvider,
)


def test_stub_position_provider_with_symbol_override() -> None:
    provider = StubPositionStateProvider(
        symbol_overrides={"ETHUSDT": {"position_size": 0.8, "position_side": "long"}}
    )
    state = asyncio.run(provider.get_position_state("binance", "ETHUSDT", account_id="main"))
    assert state["position_side"] == "long"
    assert state["position_size"] == 0.8
    assert state["position_mode"] == "one_way"
    assert state["exchange"] == "binance"
    assert state["account_id"] == "main"


def test_stub_account_provider_with_exchange_override() -> None:
    provider = StubAccountStateProvider(
        exchange_overrides={"binance": {"current_drawdown_ratio": 0.11}}
    )
    state = asyncio.run(provider.get_account_state("binance", account_id="main"))
    assert state["exchange"] == "binance"
    assert state["current_drawdown_ratio"] == 0.11
    assert state["account_id"] == "main"
    assert state["risk_state"] == "normal"


def test_stub_account_provider_normalizes_invalid_risk_state() -> None:
    provider = StubAccountStateProvider(
        exchange_overrides={"binance": {"risk_state": "XXX_STATE"}}
    )
    state = asyncio.run(provider.get_account_state("binance", account_id="main"))
    assert state["risk_state"] == "normal"
