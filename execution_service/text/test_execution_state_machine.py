from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio

from execution_service.app.service import ExecutionService
from execution_service.adapters.execution_state_store import InMemoryExecutionStateStore
from execution_service.adapters.stub_risk_policy_provider import StubRiskPolicyProvider
from execution_service.adapters.stub_state_providers import (
    StubAccountStateProvider,
    StubPositionStateProvider,
)


class _OkSink:
    async def submit(self, decision, execution_action):  # noqa: ANN001
        return {"submitted": True, "decision_id": decision.decision_id, "execution_action": execution_action}


class _FailSink:
    async def submit(self, decision, execution_action):  # noqa: ANN001
        _ = (decision, execution_action)
        raise RuntimeError("down")


def _payload(decision_id: str, direction: str = "long") -> dict:
    return {
        "decision_id": decision_id,
        "exchange": "binance",
        "symbol": "ETHUSDT",
        "direction_intent": direction,
        "confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {"suggested_policy": "follow_long_term"},
        "risk_hints": {"agent_action_hint": "add"},
    }


def test_state_machine_submitted_status() -> None:
    store = InMemoryExecutionStateStore()
    service = ExecutionService(
        position_provider=StubPositionStateProvider(),
        account_provider=StubAccountStateProvider(),
        risk_policy_provider=StubRiskPolicyProvider(),
        execution_sink=_OkSink(),  # type: ignore[arg-type]
        submit_enabled=True,
        execution_state_store=store,
    )
    asyncio.run(service.decide(_payload("dec-state-001")))
    state = asyncio.run(store.get_state("dec-state-001"))
    assert isinstance(state, dict)
    assert state["status"] == "submitted"
    assert state["last_transition"] == "submitted"
    assert state["attempts"] == 1
    assert isinstance(state["submitted_at_ms"], int)
    assert state["last_error"] == ""


def test_state_machine_failed_status_on_submit_error() -> None:
    store = InMemoryExecutionStateStore()
    service = ExecutionService(
        position_provider=StubPositionStateProvider(),
        account_provider=StubAccountStateProvider(),
        risk_policy_provider=StubRiskPolicyProvider(),
        execution_sink=_FailSink(),  # type: ignore[arg-type]
        submit_enabled=True,
        execution_state_store=store,
    )
    asyncio.run(service.decide(_payload("dec-state-002")))
    state = asyncio.run(store.get_state("dec-state-002"))
    assert isinstance(state, dict)
    assert state["status"] == "failed"
    assert state["last_transition"] == "failed"
    assert state["attempts"] == 1
    assert state["submitted_at_ms"] is None
    assert state["last_error"] == "down"


def test_state_machine_skipped_status() -> None:
    store = InMemoryExecutionStateStore()
    service = ExecutionService(
        position_provider=StubPositionStateProvider(),
        account_provider=StubAccountStateProvider(),
        risk_policy_provider=StubRiskPolicyProvider(),
        submit_enabled=False,
        execution_state_store=store,
    )
    asyncio.run(service.decide(_payload("dec-state-003", direction="none")))
    state = asyncio.run(store.get_state("dec-state-003"))
    assert isinstance(state, dict)
    assert state["status"] in {"decided", "skipped"}
    assert state["attempts"] == 0
    assert state["submitted_at_ms"] is None


def test_state_machine_terminal_status_cannot_jump_back_to_pending() -> None:
    store = InMemoryExecutionStateStore()
    service = ExecutionService(
        position_provider=StubPositionStateProvider(),
        account_provider=StubAccountStateProvider(),
        risk_policy_provider=StubRiskPolicyProvider(),
        submit_enabled=False,
        execution_state_store=store,
    )
    asyncio.run(service._save_state("dec-state-004", {"status": "failed"}))
    asyncio.run(service._save_state("dec-state-004", {"status": "pending"}))
    state = asyncio.run(store.get_state("dec-state-004"))
    assert isinstance(state, dict)
    assert state["status"] == "failed"
