from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio

from services.execution_service.app.service import ExecutionService
from services.execution_service.adapters.idempotency_store import InMemoryIdempotencyStore
from services.execution_service.adapters.stub_risk_policy_provider import StubRiskPolicyProvider
from services.execution_service.adapters.stub_state_providers import (
    StubAccountStateProvider,
    StubPositionStateProvider,
)


class _CountingSink:
    def __init__(self) -> None:
        self.count = 0

    async def submit(self, decision, execution_action):  # noqa: ANN001
        self.count += 1
        return {
            "submitted": True,
            "order_id": f"mock-{self.count}",
            "decision_id": decision.decision_id,
            "execution_action": execution_action,
        }


class _NoReleaseStore(InMemoryIdempotencyStore):
    async def release_lock(self, decision_id: str) -> None:  # noqa: ARG002
        return


def _payload(decision_id: str = "dec-idem-001") -> dict:
    return {
        "decision_id": decision_id,
        "exchange": "binance",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "confidence": {"level": "medium", "score": 0.66},
        "decision_confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {"suggested_policy": "follow_long_term"},
        "risk_hints": {"agent_action_hint": "add"},
    }


def test_idempotency_returns_cached_result_and_avoids_resubmit() -> None:
    sink = _CountingSink()
    store = InMemoryIdempotencyStore()
    service = ExecutionService(
        position_provider=StubPositionStateProvider(),
        account_provider=StubAccountStateProvider(),
        risk_policy_provider=StubRiskPolicyProvider(),
        execution_sink=sink,  # type: ignore[arg-type]
        submit_enabled=True,
        idempotency_store=store,
    )

    first = asyncio.run(service.decide(_payload("dec-idem-001")))
    second = asyncio.run(service.decide(_payload("dec-idem-001")))

    assert first.decision_id == second.decision_id
    assert sink.count == 1
    assert first.order_result == second.order_result


def test_idempotency_disabled_allows_resubmit() -> None:
    sink = _CountingSink()
    service = ExecutionService(
        position_provider=StubPositionStateProvider(),
        account_provider=StubAccountStateProvider(),
        risk_policy_provider=StubRiskPolicyProvider(),
        execution_sink=sink,  # type: ignore[arg-type]
        submit_enabled=True,
        idempotency_store=None,
    )
    asyncio.run(service.decide(_payload("dec-idem-002")))
    asyncio.run(service.decide(_payload("dec-idem-002")))
    assert sink.count == 2


def test_idempotency_lock_busy_returns_in_progress() -> None:
    sink = _CountingSink()
    store = _NoReleaseStore()
    asyncio.run(store.try_acquire_lock("dec-idem-003", 30))
    service = ExecutionService(
        position_provider=StubPositionStateProvider(),
        account_provider=StubAccountStateProvider(),
        risk_policy_provider=StubRiskPolicyProvider(),
        execution_sink=sink,  # type: ignore[arg-type]
        submit_enabled=True,
        idempotency_store=store,
        idempotency_lock_ttl_s=30,
    )
    out = asyncio.run(service.decide(_payload("dec-idem-003")))
    assert out.execution_action == "skip"
    assert out.reject_reason == "idempotency_in_progress"
    assert sink.count == 0
