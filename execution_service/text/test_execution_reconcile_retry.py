from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio

from execution_service.app.service import ExecutionService
from execution_service.adapters.stub_risk_policy_provider import StubRiskPolicyProvider
from execution_service.adapters.stub_state_providers import (
    StubAccountStateProvider,
    StubPositionStateProvider,
)


class _RetryThenOkSink:
    def __init__(self) -> None:
        self.count = 0

    async def reconcile(self, order_id, payload):  # noqa: ANN001
        self.count += 1
        if self.count == 1:
            raise RuntimeError("temporarily_unavailable")
        return {
            "mode": "mock",
            "order_id": order_id,
            "decision_id": payload.get("decision_id"),
            "status": "filled",
            "ts": 1760000000001,
        }


class _NonRetryableSink:
    async def reconcile(self, order_id, payload):  # noqa: ANN001
        _ = (order_id, payload)
        raise RuntimeError("invalid_order_id")


def test_reconcile_retry_then_success() -> None:
    service = ExecutionService(
        position_provider=StubPositionStateProvider(),
        account_provider=StubAccountStateProvider(),
        risk_policy_provider=StubRiskPolicyProvider(),
        execution_sink=_RetryThenOkSink(),  # type: ignore[arg-type]
        submit_enabled=True,
        reconcile_max_retries=1,
        reconcile_backoff_base_s=0.0,
    )
    out = asyncio.run(service.reconcile_order({"order_id": "ord-retry-001", "decision_id": "dec-retry-001"}))
    assert out["status"] == "filled"
    assert out["retry_meta"]["attempts"] == 2
    assert out["retry_meta"]["status"] == "ok"


def test_reconcile_non_retryable_error_fails_fast() -> None:
    service = ExecutionService(
        position_provider=StubPositionStateProvider(),
        account_provider=StubAccountStateProvider(),
        risk_policy_provider=StubRiskPolicyProvider(),
        execution_sink=_NonRetryableSink(),  # type: ignore[arg-type]
        submit_enabled=True,
        reconcile_max_retries=3,
        reconcile_backoff_base_s=0.0,
    )
    try:
        asyncio.run(service.reconcile_order({"order_id": "ord-retry-002", "decision_id": "dec-retry-002"}))
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        text = str(exc)
        assert "retryable=False" in text
        assert "attempts=1" in text
