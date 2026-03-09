from __future__ import annotations

import time
from typing import Any, Dict, Mapping

from execution_service.domain.contracts import DecisionIntent, ExecutionResult
from execution_service.domain.decision_engine import ExecutionDecisionEngine
from execution_service.ports.execution_sink import ExecutionSink
from execution_service.ports.account_state_provider import AccountStateProvider
from execution_service.ports.position_state_provider import PositionStateProvider
from execution_service.ports.risk_policy_provider import RiskPolicyProvider


class ExecutionService:
    """执行服务：聚合 providers 并产出最终执行裁决。"""

    def __init__(
        self,
        *,
        position_provider: PositionStateProvider,
        account_provider: AccountStateProvider,
        risk_policy_provider: RiskPolicyProvider,
        execution_sink: ExecutionSink | None = None,
        submit_enabled: bool = False,
    ) -> None:
        self._position_provider = position_provider
        self._account_provider = account_provider
        self._risk_policy_provider = risk_policy_provider
        self._execution_sink = execution_sink
        self._submit_enabled = bool(submit_enabled)

    async def decide(self, payload: Mapping[str, Any]) -> ExecutionResult:
        decision = DecisionIntent.from_dict(payload)
        position_state = await self._position_provider.get_position_state(
            decision.exchange,
            decision.symbol,
        )
        account_state = await self._account_provider.get_account_state(decision.exchange)
        risk_policy = await self._risk_policy_provider.get_risk_policy(
            decision.exchange,
            decision.symbol,
        )
        result = ExecutionDecisionEngine.decide(
            decision,
            position_state=dict(position_state or {}),
            account_state=dict(account_state or {}),
            risk_policy=dict(risk_policy or {}),
        )
        if (
            self._submit_enabled
            and self._execution_sink is not None
            and result.reject_reason is None
            and result.execution_action in {"add", "reduce", "exit"}
        ):
            try:
                order_result = await self._execution_sink.submit(decision, result.execution_action)
                result = ExecutionResult.from_dict(
                    {
                        "decision_id": result.decision_id,
                        "execution_action": result.execution_action,
                        "reject_reason": result.reject_reason,
                        "applied_risk_rules": list(result.applied_risk_rules),
                        "order_result": dict(order_result or {}),
                        "notes": result.notes,
                    }
                )
            except Exception as exc:  # pragma: no cover
                # 中文注释：执行下沉异常时不抛 5xx，转为业务可观测降级，避免阻塞主决策链路。
                result = ExecutionResult.from_dict(
                    {
                        "decision_id": result.decision_id,
                        "execution_action": "skip",
                        "reject_reason": "execution_submit_failed",
                        "applied_risk_rules": [*list(result.applied_risk_rules), "execution_submit_fallback"],
                        "notes": f"{result.notes or ''}; execution_submit_failed:{exc}".strip("; "),
                    }
                )
        return result

    async def get_debug_state(self, *, exchange: str, symbol: str, redact: bool = False) -> Dict[str, Any]:
        """只读调试视图：便于联调时检查 execution 输入状态。"""

        position_state = await self._position_provider.get_position_state(exchange, symbol)
        account_state = await self._account_provider.get_account_state(exchange)
        risk_policy = await self._risk_policy_provider.get_risk_policy(exchange, symbol)
        position_state_out = dict(position_state or {})
        account_state_out = dict(account_state or {})
        if redact:
            _apply_redaction(position_state_out, account_state_out)
        return {
            "exchange": exchange,
            "symbol": symbol,
            "position_state": position_state_out,
            "account_state": account_state_out,
            "risk_policy": dict(risk_policy or {}),
            "redacted": bool(redact),
            "ts": int(time.time() * 1000),
        }


def _apply_redaction(position_state: Dict[str, Any], account_state: Dict[str, Any]) -> None:
    """脱敏敏感字段，供调试接口按需返回。"""

    for key in ("unrealized_pnl",):
        if key in position_state:
            position_state[key] = "***"
    for key in ("account_equity", "available_balance"):
        if key in account_state:
            account_state[key] = "***"
