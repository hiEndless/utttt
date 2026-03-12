from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
from dataclasses import asdict

from services.agent_server_new.domain.contracts import Confidence, ExecutionPlan, RiskAllowance
from services.execution_service.adapters.agent_execution_plan_adapter import (
    adapt_agent_execution_plan_to_decision_intent,
)
from services.execution_service.adapters.stub_risk_policy_provider import StubRiskPolicyProvider
from services.execution_service.adapters.stub_state_providers import (
    StubAccountStateProvider,
    StubPositionStateProvider,
)
from services.execution_service.app.service import ExecutionService


def test_agent_plan_to_execution_service_smoke() -> None:
    plan = ExecutionPlan(
        action="add",
        direction="long",
        allowance=RiskAllowance(
            allow_open=True,
            allow_add=True,
            allow_reduce=True,
            allow_exit=True,
            reasons=[],
        ),
        confidence=Confidence(level="medium", score=0.65),
        notes="agent建议顺势尝试开仓",
    )
    decision_payload = adapt_agent_execution_plan_to_decision_intent(
        decision_id="dec-agent-001",
        exchange="binance",
        symbol="ETHUSDT",
        plan=asdict(plan),
        cross_horizon_policy={"suggested_policy": "follow_long_term"},
    )
    service = ExecutionService(
        position_provider=StubPositionStateProvider(),
        account_provider=StubAccountStateProvider(),
        risk_policy_provider=StubRiskPolicyProvider(),
    )
    result = asyncio.run(service.decide(decision_payload))
    assert result.decision_id == "dec-agent-001"
    assert result.execution_action in {"add", "reduce", "hold", "exit", "skip"}


def test_agent_execution_adapter_prefers_decision_confidence_and_keeps_risk_hints() -> None:
    payload = adapt_agent_execution_plan_to_decision_intent(
        decision_id="dec-agent-002",
        exchange="binance",
        symbol="ETHUSDT",
        plan={
            "action": "add",
            "direction": "long",
            "confidence": {"level": "low", "score": 0.2},
            "decision_confidence": {"level": "high", "score": 0.91},
            "notes": "prefer trend continuation",
        },
        cross_horizon_policy={"suggested_policy": "follow_long_term"},
    )
    assert payload["confidence"] == {"level": "high", "score": 0.91}
    assert payload["decision_confidence"] == {"level": "high", "score": 0.91}
    assert payload["risk_hints"]["decision_confidence"] == {"level": "high", "score": 0.91}
    assert payload["risk_hints"]["agent_action_hint"] == "add"
    assert payload["risk_hints"]["agent_notes"] == "prefer trend continuation"
