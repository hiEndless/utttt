from __future__ import annotations

import time
import asyncio
import logging
from typing import Any, Dict, Mapping

from services.execution_service.domain.contracts import DecisionIntent, ExecutionResult
from services.execution_service.domain.decision_engine import ExecutionDecisionEngine
from services.execution_service.domain.reconcile_codes import (
    RECONCILE_REASON_IN_PROGRESS,
    RECONCILE_REASON_NON_RETRYABLE_ERROR,
    RECONCILE_REASON_RETRY_EXHAUSTED,
)
from services.execution_service.domain.reconcile_statuses import (
    RECONCILE_STATUS_CANCELED,
    RECONCILE_STATUS_FAILED,
    RECONCILE_STATUS_SUBMITTED,
    RECONCILE_STATUSES,
)
from services.execution_service.domain.retry_meta import RETRY_META_STATUS_FAILED, RETRY_META_STATUS_OK
from services.execution_service.version import RULESET_VERSION
from services.execution_service.ports.execution_sink import ExecutionSink
from services.execution_service.ports.execution_state_store import ExecutionStateStore
from services.execution_service.ports.idempotency_store import IdempotencyStore
from services.execution_service.ports.account_state_provider import AccountStateProvider
from services.execution_service.ports.position_state_provider import PositionStateProvider
from services.execution_service.ports.risk_policy_provider import RiskPolicyProvider
from services.execution_service.ports.confidence_metrics_store import ConfidenceMetricsStore
from services.execution_service.adapters.confidence_metrics_store import InMemoryConfidenceMetricsStore

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
        reconcile_max_retries: int = 0,
        reconcile_backoff_base_s: float = 0.2,
        confidence_metrics_store: ConfidenceMetricsStore | None = None,
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
        self._reconcile_max_retries = max(0, int(reconcile_max_retries))
        self._reconcile_backoff_base_s = max(0.0, float(reconcile_backoff_base_s))
        self._confidence_metrics_store = confidence_metrics_store or InMemoryConfidenceMetricsStore()

    async def decide(self, payload: Mapping[str, Any]) -> ExecutionResult:
        await self._record_confidence_metrics_from_payload(payload)
        try:
            decision = DecisionIntent.from_dict(payload)
        except ValueError as exc:
            if "confidence 与 decision_confidence 不一致" in str(exc):
                await self._confidence_metrics_store.record_mismatch_rejection()
            raise
        account_id = decision.account_id
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
                "account_id": account_id,
                "source": "execution_service",
                "state_source": "execution_service",
                "trace_id": decision.trace_id,
            },
        )

        try:
            position_state = await self._position_provider.get_position_state(
                decision.exchange,
                decision.symbol,
                account_id=account_id,
            )
            account_state = await self._account_provider.get_account_state(decision.exchange, account_id=account_id)
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
            policy_snapshot = _build_policy_snapshot(risk_policy)
            result = ExecutionResult.from_dict(
                {
                    **result.to_dict(),
                    "policy_snapshot": policy_snapshot,
                }
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
                    "account_id": account_id,
                    "execution_action": result.execution_action,
                    "reject_reason": result.reject_reason,
                    "attempts": _extract_attempts(result),
                    "submitted_at_ms": _extract_submitted_at_ms(result),
                    "last_error": _extract_last_error(result),
                    "risk_state": _extract_risk_state(result),
                    "rule_debug": _extract_rule_debug(result),
                    "policy_snapshot": _extract_policy_snapshot(result),
                    "source": "execution_service",
                    "state_source": _derive_decision_state_source(result),
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
        account_id: str = "main",
        redact: bool = False,
        decision_id: str | None = None,
    ) -> Dict[str, Any]:
        """只读调试视图：便于联调时检查 execution 输入状态。"""

        account_id = str(account_id or "").strip() or "main"
        position_state = await self._position_provider.get_position_state(exchange, symbol, account_id=account_id)
        account_state = await self._account_provider.get_account_state(exchange, account_id=account_id)
        risk_policy = await self._risk_policy_provider.get_risk_policy(exchange, symbol)
        position_state_out = dict(position_state or {})
        account_state_out = dict(account_state or {})
        if redact:
            _apply_redaction(position_state_out, account_state_out)
        confidence_metrics = await self._confidence_metrics_store.snapshot()
        out = {
            "exchange": exchange,
            "account_id": account_id,
            "symbol": symbol,
            "position_state": position_state_out,
            "account_state": account_state_out,
            "risk_policy": dict(risk_policy or {}),
            "confidence_migration": _build_confidence_migration_view(confidence_metrics),
            "redacted": bool(redact),
            "ts": int(time.time() * 1000),
        }
        out["ts_ms"] = int(out["ts"])
        if decision_id and self._execution_state_store is not None:
            out["decision_state"] = await self._execution_state_store.get_state(str(decision_id))
        return out

    async def get_confidence_migration_metrics(self) -> Dict[str, int]:
        return await self._confidence_metrics_store.snapshot()

    async def reset_confidence_migration_metrics(self) -> None:
        await self._confidence_metrics_store.reset()

    async def reconcile_order(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        order_id = str(payload.get("order_id") or "").strip()
        account_id = str(payload.get("account_id") or "").strip() or "main"
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
                now_ms = int(time.time() * 1000)
                return {
                    "mode": _infer_sink_mode(self._execution_sink),
                    "order_id": order_id,
                    "account_id": account_id,
                    "status": RECONCILE_STATUS_SUBMITTED,
                    "status_source": "execution_service",
                    "reconcile_status": RECONCILE_STATUS_SUBMITTED,
                    "reconcile_status_source": "execution_service",
                    "sink_mode": _infer_sink_mode(self._execution_sink),
                    "idempotency_hit": False,
                    "reason_code": RECONCILE_REASON_IN_PROGRESS,
                    "note": "相同 order_id 的回执对账正在处理中，请稍后重试",
                    "ts": now_ms,
                    "ts_ms": now_ms,
                }
        if self._execution_sink is None:
            raise RuntimeError("execution_sink_not_configured")
        reconcile_fn = getattr(self._execution_sink, "reconcile", None)
        if not callable(reconcile_fn):
            raise RuntimeError("execution_sink_reconcile_not_supported")
        try:
            out = await self._reconcile_with_retry(
                reconcile_fn=reconcile_fn,
                order_id=order_id,
                payload=payload,
            )
            out = _normalize_reconcile_output(out, default_status_source="execution_sink")
            out.setdefault("mode", _infer_sink_mode(self._execution_sink))
            out.setdefault("order_id", order_id)
            out.setdefault("account_id", account_id)
            out.setdefault("ts", int(time.time() * 1000))
            out.setdefault("ts_ms", int(out["ts"]))
            out["idempotency_hit"] = False
            decision_id = str(out.get("decision_id") or payload.get("decision_id") or "").strip()
            reconcile_status = _normalize_reconcile_status(str(out.get("status") or ""))
            if decision_id and reconcile_status is not None:
                await self._save_state(
                    decision_id,
                    {
                        "status": reconcile_status,
                        "last_transition": reconcile_status,
                        "account_id": account_id,
                        "source": "execution_service",
                        "state_source": str(out.get("reconcile_status_source") or "execution_service").strip().lower()
                        or "execution_service",
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

    async def _reconcile_with_retry(
        self,
        *,
        reconcile_fn: Any,
        order_id: str,
        payload: Mapping[str, Any],
    ) -> Dict[str, Any]:
        attempts = 0
        last_error = ""
        max_attempts = 1 + self._reconcile_max_retries
        while attempts < max_attempts:
            attempts += 1
            try:
                out = dict(await reconcile_fn(order_id, payload) or {})
                out["retry_meta"] = {
                    "attempts": attempts,
                    "max_retries": self._reconcile_max_retries,
                    "status": RETRY_META_STATUS_OK,
                }
                return out
            except Exception as exc:  # pragma: no cover
                last_error = str(exc)
                retryable = _is_retryable_reconcile_error(exc)
                if (not retryable) or attempts >= max_attempts:
                    return {
                        "order_id": str(order_id),
                        "account_id": str(payload.get("account_id") or "").strip() or "main",
                        "decision_id": str(payload.get("decision_id") or "").strip() or None,
                        "exchange": str(payload.get("exchange") or "").strip() or None,
                        "symbol": str(payload.get("symbol") or "").strip().upper() or None,
                        "status": RECONCILE_STATUS_FAILED,
                        "reason_code": (
                            RECONCILE_REASON_RETRY_EXHAUSTED if retryable else RECONCILE_REASON_NON_RETRYABLE_ERROR
                        ),
                        "error_message": last_error,
                        "retry_meta": {
                            "attempts": attempts,
                            "max_retries": self._reconcile_max_retries,
                            "status": RETRY_META_STATUS_FAILED,
                            "retryable": bool(retryable),
                        },
                    }
                backoff_s = self._reconcile_backoff_base_s * (2 ** (attempts - 1))
                if backoff_s > 0:
                    await asyncio.sleep(backoff_s)

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
        payload["account_id"] = str(payload.get("account_id") or "").strip() or "main"
        payload["source"] = "execution_service"
        payload["state_source"] = _normalize_decision_state_source(payload.get("state_source"))
        payload["updated_at_ms"] = int(time.time() * 1000)
        await self._execution_state_store.save_state(str(decision_id), payload)

    async def _record_confidence_metrics_from_payload(self, payload: Mapping[str, Any]) -> None:
        has_conf = payload.get("confidence") is not None
        has_decision_conf = payload.get("decision_confidence") is not None
        await self._confidence_metrics_store.record_decide_request(
            has_confidence=bool(has_conf),
            has_decision_confidence=bool(has_decision_conf),
        )

    async def _submit_with_retry(self, *, decision: DecisionIntent, result: ExecutionResult) -> ExecutionResult:
        attempts = 0
        last_error = ""
        max_attempts = 1 + self._submit_max_retries
        while attempts < max_attempts:
            attempts += 1
            try:
                order_result = await self._execution_sink.submit(decision, result.execution_action)  # type: ignore[union-attr]
                payload = dict(order_result or {})
                payload = _normalize_order_result_payload(payload, execution_sink=self._execution_sink)
                payload["submitted_at_ms"] = int(time.time() * 1000)
                payload["retry_meta"] = {
                    "attempts": attempts,
                    "max_retries": self._submit_max_retries,
                    "status": RETRY_META_STATUS_OK,
                }
                return ExecutionResult.from_dict(
                    {
                        "decision_id": result.decision_id,
                        "execution_action": result.execution_action,
                        "reject_reason": result.reject_reason,
                        "applied_risk_rules": list(result.applied_risk_rules),
                        "order_result": payload,
                        "policy_snapshot": result.policy_snapshot,
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
                    "mode": _infer_sink_mode(self._execution_sink),
                    "sink_mode": _infer_sink_mode(self._execution_sink),
                    "status": RECONCILE_STATUS_FAILED,
                    "status_source": "execution_service",
                    "order_status": RECONCILE_STATUS_FAILED,
                    "order_status_source": "execution_service",
                    "retry_meta": {
                        "attempts": max_attempts,
                        "max_retries": self._submit_max_retries,
                        "status": RETRY_META_STATUS_FAILED,
                        "last_error": last_error,
                    }
                },
                "policy_snapshot": result.policy_snapshot,
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


def _extract_rule_debug(result: ExecutionResult) -> Dict[str, Any]:
    signal_result = result.signal_result if isinstance(result.signal_result, dict) else {}
    rule_debug = signal_result.get("rule_debug") if isinstance(signal_result, dict) else None
    return dict(rule_debug) if isinstance(rule_debug, dict) else {}


def _extract_risk_state(result: ExecutionResult) -> str:
    signal_result = result.signal_result if isinstance(result.signal_result, dict) else {}
    risk_state = signal_result.get("risk_state") if isinstance(signal_result, dict) else None
    risk_state_str = str(risk_state or "").strip().lower()
    if risk_state_str in {"normal", "warn", "reduce_only", "frozen"}:
        return risk_state_str
    return "normal"


def _extract_policy_snapshot(result: ExecutionResult) -> Dict[str, str]:
    snapshot = result.policy_snapshot if isinstance(result.policy_snapshot, dict) else {}
    policy_version = str(snapshot.get("policy_version") or "").strip()
    ruleset_hash = str(snapshot.get("ruleset_hash") or "").strip()
    if policy_version and ruleset_hash:
        return {
            "policy_version": policy_version,
            "ruleset_hash": ruleset_hash,
        }
    return {}


def _build_policy_snapshot(risk_policy: Mapping[str, Any]) -> Dict[str, str]:
    """从当前生效风控策略提取可回放的版本快照。"""

    policy_version = str((risk_policy or {}).get("policy_version") or "").strip() or "risk-policy-default-v1"
    ruleset_hash = str((risk_policy or {}).get("ruleset_hash") or "").strip() or RULESET_VERSION
    return {
        "policy_version": policy_version,
        "ruleset_hash": ruleset_hash,
    }


def _derive_decision_state_source(result: ExecutionResult) -> str:
    order_result = result.order_result if isinstance(result.order_result, dict) else {}
    if isinstance(order_result, dict) and order_result:
        src = _normalize_decision_state_source(order_result.get("order_status_source"))
        if src != "execution_service":
            return src
        if str(result.reject_reason or "").strip() == "execution_submit_failed":
            return "execution_service"
        return src
    return "decision_engine"


def _normalize_decision_state_source(raw: Any) -> str:
    src = str(raw or "").strip().lower()
    if src in {"decision_engine", "execution_sink", "execution_service"}:
        return src
    return "execution_service"


def _build_confidence_migration_view(metrics: Mapping[str, Any]) -> Dict[str, Any]:
    m = {
        "decide_requests_total": int((metrics or {}).get("decide_requests_total") or 0),
        "confidence_only_requests": int((metrics or {}).get("confidence_only_requests") or 0),
        "decision_confidence_requests": int((metrics or {}).get("decision_confidence_requests") or 0),
        "confidence_alias_mismatch_rejections": int((metrics or {}).get("confidence_alias_mismatch_rejections") or 0),
    }
    readiness = {
        "confidence_only_zero": m["confidence_only_requests"] == 0,
        "alias_mismatch_zero": m["confidence_alias_mismatch_rejections"] == 0,
    }
    return {"metrics": m, "v2_cutover_readiness": readiness}


def _normalize_reconcile_status(status: str) -> str | None:
    normalized = str(status or "").strip().lower()
    if normalized in set(RECONCILE_STATUSES) | {"cancelled"}:
        if normalized == "cancelled":
            return RECONCILE_STATUS_CANCELED
        return normalized
    return None


def _reconcile_cache_key(order_id: str) -> str:
    return f"reconcile:{str(order_id).strip()}"


def _is_retryable_reconcile_error(exc: Exception) -> bool:
    msg = str(exc or "").strip().lower()
    retryable_signals = (
        "timeout",
        "timed out",
        "too many requests",
        "temporarily unavailable",
        "temporarily_unavailable",
        "connection reset",
        "connection aborted",
        "connection refused",
        "429",
    )
    return any(token in msg for token in retryable_signals)


def _infer_sink_mode(execution_sink: Any) -> str:
    if execution_sink is None:
        return "exchange"
    cls_name = str(getattr(execution_sink, "__class__", type(execution_sink)).__name__).lower()
    if "exchange" in cls_name:
        return "exchange"
    return "exchange"


def _normalize_order_result_payload(payload: Dict[str, Any], *, execution_sink: Any) -> Dict[str, Any]:
    out = dict(payload or {})
    sink_mode = str(out.get("mode") or "").strip().lower() or _infer_sink_mode(execution_sink)
    out["mode"] = sink_mode
    out["sink_mode"] = sink_mode
    status = str(out.get("status") or "").strip().lower()
    if status not in set(RECONCILE_STATUSES):
        status = RECONCILE_STATUS_SUBMITTED if bool(out.get("submitted")) else RECONCILE_STATUS_FAILED
    out["status"] = status
    out["status_source"] = str(out.get("status_source") or "execution_sink").strip() or "execution_sink"
    out["order_status"] = str(out.get("order_status") or status).strip().lower() or status
    out["order_status_source"] = str(out.get("order_status_source") or out["status_source"]).strip() or out["status_source"]
    return out


def _normalize_reconcile_output(out: Mapping[str, Any], *, default_status_source: str) -> Dict[str, Any]:
    payload = dict(out or {})
    status = str(payload.get("status") or "").strip().lower()
    if status not in set(RECONCILE_STATUSES):
        status = RECONCILE_STATUS_FAILED
    payload["status"] = status
    payload["status_source"] = str(payload.get("status_source") or default_status_source).strip() or default_status_source
    payload["reconcile_status"] = str(payload.get("reconcile_status") or status).strip().lower() or status
    payload["reconcile_status_source"] = (
        str(payload.get("reconcile_status_source") or payload["status_source"]).strip() or payload["status_source"]
    )
    payload["sink_mode"] = str(payload.get("sink_mode") or payload.get("mode") or "exchange").strip().lower() or "exchange"
    return payload
