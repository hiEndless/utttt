from __future__ import annotations

import time
import asyncio
import logging
from typing import Any, Dict, Mapping

from execution_service.domain.contracts import DecisionIntent, ExecutionResult
from execution_service.domain.decision_engine import ExecutionDecisionEngine
from execution_service.ports.execution_sink import ExecutionSink
from execution_service.ports.execution_state_store import ExecutionStateStore
from execution_service.ports.idempotency_store import IdempotencyStore
from execution_service.ports.account_state_provider import AccountStateProvider
from execution_service.ports.position_state_provider import PositionStateProvider
from execution_service.ports.risk_policy_provider import RiskPolicyProvider

logger = logging.getLogger(__name__)


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
        idempotency_store: IdempotencyStore | None = None,
        idempotency_lock_ttl_s: int = 30,
        execution_state_store: ExecutionStateStore | None = None,
        submit_max_retries: int = 0,
        submit_backoff_base_s: float = 0.2,
    ) -> None:
        self._position_provider = position_provider
        self._account_provider = account_provider
        self._risk_policy_provider = risk_policy_provider
        self._execution_sink = execution_sink
        self._submit_enabled = bool(submit_enabled)
        self._idempotency_store = idempotency_store
        self._idempotency_lock_ttl_s = int(idempotency_lock_ttl_s)
        self._execution_state_store = execution_state_store
        self._submit_max_retries = max(0, int(submit_max_retries))
        self._submit_backoff_base_s = max(0.0, float(submit_backoff_base_s))

    async def decide(self, payload: Mapping[str, Any]) -> ExecutionResult:
        decision = DecisionIntent.from_dict(payload)
        lock_acquired = False
        if self._idempotency_store is not None:
            cached = await self._idempotency_store.get_result(decision.decision_id)
            if isinstance(cached, dict) and cached:
                return ExecutionResult.from_dict(cached)
            lock_acquired = await self._idempotency_store.try_acquire_lock(
                decision.decision_id,
                self._idempotency_lock_ttl_s,
            )
            if not lock_acquired:
                cached_after_lock_fail = await self._idempotency_store.get_result(decision.decision_id)
                if isinstance(cached_after_lock_fail, dict) and cached_after_lock_fail:
                    return ExecutionResult.from_dict(cached_after_lock_fail)
                return ExecutionResult.from_dict(
                    {
                        "decision_id": decision.decision_id,
                        "execution_action": "skip",
                        "reject_reason": "idempotency_in_progress",
                        "applied_risk_rules": ["idempotency_lock_busy"],
                        "notes": "相同 decision_id 正在处理，请稍后重试",
                    }
                )
        await self._save_state(
            decision.decision_id,
            {
                "status": "pending",
                "source": "execution_service",
                "trace_id": decision.trace_id,
            },
        )

        try:
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
                result = await self._submit_with_retry(decision=decision, result=result)

            if self._idempotency_store is not None:
                await self._idempotency_store.save_result(decision.decision_id, result.to_dict())
            await self._save_state(
                decision.decision_id,
                {
                    "status": _derive_execution_status(result),
                    "last_transition": _derive_execution_status(result),
                    "execution_action": result.execution_action,
                    "reject_reason": result.reject_reason,
                    "attempts": _extract_attempts(result),
                    "submitted_at_ms": _extract_submitted_at_ms(result),
                    "last_error": _extract_last_error(result),
                    "source": "execution_service",
                    "trace_id": decision.trace_id,
                },
            )
            return result
        finally:
            if self._idempotency_store is not None and lock_acquired:
                await self._idempotency_store.release_lock(decision.decision_id)

    async def get_debug_state(
        self,
        *,
        exchange: str,
        symbol: str,
        redact: bool = False,
        decision_id: str | None = None,
    ) -> Dict[str, Any]:
        """只读调试视图：便于联调时检查 execution 输入状态。"""

        position_state = await self._position_provider.get_position_state(exchange, symbol)
        account_state = await self._account_provider.get_account_state(exchange)
        risk_policy = await self._risk_policy_provider.get_risk_policy(exchange, symbol)
        position_state_out = dict(position_state or {})
        account_state_out = dict(account_state or {})
        if redact:
            _apply_redaction(position_state_out, account_state_out)
        out = {
            "exchange": exchange,
            "symbol": symbol,
            "position_state": position_state_out,
            "account_state": account_state_out,
            "risk_policy": dict(risk_policy or {}),
            "redacted": bool(redact),
            "ts": int(time.time() * 1000),
        }
        if decision_id and self._execution_state_store is not None:
            out["decision_state"] = await self._execution_state_store.get_state(str(decision_id))
        return out

    async def reconcile_order(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        order_id = str(payload.get("order_id") or "").strip()
        if not order_id:
            raise ValueError("order_id 不能为空")
        cache_key = _reconcile_cache_key(order_id)
        reconcile_lock_acquired = False
        if self._idempotency_store is not None:
            cached = await self._idempotency_store.get_result(cache_key)
            if isinstance(cached, dict) and cached:
                out_cached = dict(cached)
                out_cached["idempotency_hit"] = True
                return out_cached
            reconcile_lock_acquired = await self._idempotency_store.try_acquire_lock(
                cache_key,
                self._idempotency_lock_ttl_s,
            )
            if not reconcile_lock_acquired:
                cached_after_lock_fail = await self._idempotency_store.get_result(cache_key)
                if isinstance(cached_after_lock_fail, dict) and cached_after_lock_fail:
                    out_cached = dict(cached_after_lock_fail)
                    out_cached["idempotency_hit"] = True
                    return out_cached
                return {
                    "order_id": order_id,
                    "status": "submitted",
                    "idempotency_hit": False,
                    "reject_reason": "reconcile_in_progress",
                    "note": "相同 order_id 的回执对账正在处理中，请稍后重试",
                    "ts": int(time.time() * 1000),
                }
        if self._execution_sink is None:
            raise RuntimeError("execution_sink_not_configured")
        reconcile_fn = getattr(self._execution_sink, "reconcile", None)
        if not callable(reconcile_fn):
            raise RuntimeError("execution_sink_reconcile_not_supported")
        try:
            result = await reconcile_fn(order_id, payload)  # type: ignore[misc]
            out = dict(result or {})
            out.setdefault("order_id", order_id)
            out.setdefault("ts", int(time.time() * 1000))
            out["idempotency_hit"] = False
            decision_id = str(out.get("decision_id") or payload.get("decision_id") or "").strip()
            reconcile_status = _normalize_reconcile_status(str(out.get("status") or ""))
            if decision_id and reconcile_status is not None:
                await self._save_state(
                    decision_id,
                    {
                        "status": reconcile_status,
                        "last_transition": reconcile_status,
                        "source": "execution_service",
                        "trace_id": str(payload.get("trace_id") or "").strip() or None,
                        "reconcile_order_id": order_id,
                        "reconcile_status_raw": str(out.get("status") or "").strip().lower() or None,
                    },
                )
            if self._idempotency_store is not None:
                await self._idempotency_store.save_result(cache_key, out)
            return out
        finally:
            if self._idempotency_store is not None and reconcile_lock_acquired:
                await self._idempotency_store.release_lock(cache_key)

    async def _save_state(self, decision_id: str, state: Dict[str, Any]) -> None:
        if self._execution_state_store is None:
            return
        prev = await self._execution_state_store.get_state(str(decision_id))
        prev_status = prev.get("status") if isinstance(prev, dict) else None
        next_status = state.get("status")
        if isinstance(prev_status, str) and isinstance(next_status, str):
            if not _is_valid_state_transition(prev_status, next_status):
                logger.warning(
                    "执行状态机拒绝非法跃迁 decision_id=%s from=%s to=%s",
                    str(decision_id),
                    prev_status,
                    next_status,
                )
                return
        payload = dict(prev or {})
        payload.update(dict(state or {}))
        payload["decision_id"] = str(decision_id)
        payload["updated_at_ms"] = int(time.time() * 1000)
        await self._execution_state_store.save_state(str(decision_id), payload)

    async def _submit_with_retry(self, *, decision: DecisionIntent, result: ExecutionResult) -> ExecutionResult:
        attempts = 0
        last_error = ""
        max_attempts = 1 + self._submit_max_retries
        while attempts < max_attempts:
            attempts += 1
            try:
                order_result = await self._execution_sink.submit(decision, result.execution_action)  # type: ignore[union-attr]
                payload = dict(order_result or {})
                payload["submitted_at_ms"] = int(time.time() * 1000)
                payload["retry_meta"] = {
                    "attempts": attempts,
                    "max_retries": self._submit_max_retries,
                    "status": "ok",
                }
                return ExecutionResult.from_dict(
                    {
                        "decision_id": result.decision_id,
                        "execution_action": result.execution_action,
                        "reject_reason": result.reject_reason,
                        "applied_risk_rules": list(result.applied_risk_rules),
                        "order_result": payload,
                        "notes": result.notes,
                    }
                )
            except Exception as exc:  # pragma: no cover
                last_error = str(exc)
                if attempts >= max_attempts:
                    break
                backoff_s = self._submit_backoff_base_s * (2 ** (attempts - 1))
                if backoff_s > 0:
                    await asyncio.sleep(backoff_s)
        # 中文注释：执行下沉异常时不抛 5xx，转为业务可观测降级，避免阻塞主决策链路。
        return ExecutionResult.from_dict(
            {
                "decision_id": result.decision_id,
                "execution_action": "skip",
                "reject_reason": "execution_submit_failed",
                "applied_risk_rules": [*list(result.applied_risk_rules), "execution_submit_fallback"],
                "order_result": {
                    "retry_meta": {
                        "attempts": max_attempts,
                        "max_retries": self._submit_max_retries,
                        "status": "failed",
                        "last_error": last_error,
                    }
                },
                "notes": f"{result.notes or ''}; execution_submit_failed:{last_error}".strip("; "),
            }
        )


def _derive_execution_status(result: ExecutionResult) -> str:
    if result.reject_reason == "execution_submit_failed":
        return "failed"
    if result.reject_reason:
        return "skipped"
    if result.execution_action in {"add", "reduce", "exit"} and result.order_result is not None:
        return "submitted"
    return "decided"


def _is_valid_state_transition(prev_status: str, next_status: str) -> bool:
    if prev_status == next_status:
        return True
    allowed = {
        "pending": {"pending", "submitted", "failed", "skipped", "decided"},
        "submitted": {"submitted", "filled", "canceled", "rejected", "failed"},
        "failed": {"failed"},
        "skipped": {"skipped"},
        "decided": {"decided"},
        "filled": {"filled"},
        "canceled": {"canceled"},
        "rejected": {"rejected"},
    }
    next_set = allowed.get(str(prev_status), set())
    return str(next_status) in next_set


def _apply_redaction(position_state: Dict[str, Any], account_state: Dict[str, Any]) -> None:
    """脱敏敏感字段，供调试接口按需返回。"""

    for key in ("unrealized_pnl",):
        if key in position_state:
            position_state[key] = "***"
    for key in ("account_equity", "available_balance"):
        if key in account_state:
            account_state[key] = "***"


def _extract_attempts(result: ExecutionResult) -> int:
    order_result = result.order_result if isinstance(result.order_result, dict) else {}
    retry_meta = order_result.get("retry_meta") if isinstance(order_result.get("retry_meta"), dict) else {}
    attempts = retry_meta.get("attempts")
    if isinstance(attempts, int) and attempts >= 0:
        return attempts
    return 0


def _extract_submitted_at_ms(result: ExecutionResult) -> int | None:
    order_result = result.order_result if isinstance(result.order_result, dict) else {}
    submitted_at_ms = order_result.get("submitted_at_ms")
    if isinstance(submitted_at_ms, int) and submitted_at_ms > 0:
        return submitted_at_ms
    return None


def _extract_last_error(result: ExecutionResult) -> str:
    order_result = result.order_result if isinstance(result.order_result, dict) else {}
    retry_meta = order_result.get("retry_meta") if isinstance(order_result.get("retry_meta"), dict) else {}
    last_error = retry_meta.get("last_error")
    return str(last_error) if last_error else ""


def _normalize_reconcile_status(status: str) -> str | None:
    normalized = str(status or "").strip().lower()
    if normalized in {"filled", "canceled", "cancelled", "rejected", "submitted", "failed"}:
        if normalized == "cancelled":
            return "canceled"
        return normalized
    return None


def _reconcile_cache_key(order_id: str) -> str:
    return f"reconcile:{str(order_id).strip()}"
