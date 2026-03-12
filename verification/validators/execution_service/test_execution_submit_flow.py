from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio

from services.execution_service.app.service import ExecutionService
from services.execution_service.adapters.stub_risk_policy_provider import StubRiskPolicyProvider
from services.execution_service.adapters.stub_state_providers import (
    StubAccountStateProvider,
    StubPositionStateProvider,
)


class _OkSink:
    async def submit(self, decision, execution_action):  # noqa: ANN001
        return {
            "submitted": True,
            "order_id": "mock-001",
            "decision_id": decision.decision_id,
            "execution_action": execution_action,
        }


class _FailSink:
    async def submit(self, decision, execution_action):  # noqa: ANN001
        _ = (decision, execution_action)
        raise RuntimeError("sink_down")


class _FlakySink:
    def __init__(self) -> None:
        self.count = 0

    async def submit(self, decision, execution_action):  # noqa: ANN001
        self.count += 1
        if self.count == 1:
            raise RuntimeError("temporary_down")
        return {
            "submitted": True,
            "order_id": "mock-retry-001",
            "decision_id": decision.decision_id,
            "execution_action": execution_action,
        }


def _payload() -> dict:
    return {
        "decision_id": "dec-submit-001",
        "exchange": "binance",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "confidence": {"level": "medium", "score": 0.66},
        "decision_confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {"suggested_policy": "follow_long_term"},
        "risk_hints": {"agent_action_hint": "add"},
    }


def test_submit_success_backfills_order_result() -> None:
    service = ExecutionService(
        position_provider=StubPositionStateProvider(),
        account_provider=StubAccountStateProvider(),
        risk_policy_provider=StubRiskPolicyProvider(),
        execution_sink=_OkSink(),  # type: ignore[arg-type]
        submit_enabled=True,
    )
    out = asyncio.run(service.decide(_payload()))
    assert out.execution_action == "add"
    assert out.reject_reason is None
    assert isinstance(out.order_result, dict)
    assert out.order_result["order_id"] == "mock-001"


def test_submit_failure_fallback_to_skip() -> None:
    service = ExecutionService(
        position_provider=StubPositionStateProvider(),
        account_provider=StubAccountStateProvider(),
        risk_policy_provider=StubRiskPolicyProvider(),
        execution_sink=_FailSink(),  # type: ignore[arg-type]
        submit_enabled=True,
    )
    out = asyncio.run(service.decide(_payload()))
    assert out.execution_action == "skip"
    assert out.reject_reason == "execution_submit_failed"
    assert isinstance(out.order_result, dict)
    assert out.order_result["retry_meta"]["status"] == "failed"


def test_submit_retry_then_success() -> None:
    sink = _FlakySink()
    service = ExecutionService(
        position_provider=StubPositionStateProvider(),
        account_provider=StubAccountStateProvider(),
        risk_policy_provider=StubRiskPolicyProvider(),
        execution_sink=sink,  # type: ignore[arg-type]
        submit_enabled=True,
        submit_max_retries=1,
        submit_backoff_base_s=0,
    )
    out = asyncio.run(service.decide(_payload()))
    assert out.execution_action == "add"
    assert out.reject_reason is None
    assert isinstance(out.order_result, dict)
    assert out.order_result["order_id"] == "mock-retry-001"
    assert out.order_result["retry_meta"]["attempts"] == 2
