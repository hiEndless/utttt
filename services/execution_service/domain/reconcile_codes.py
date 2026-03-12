from __future__ import annotations

# 中文注释：reconcile 错误码单点定义，避免代码与 schema 枚举漂移。
RECONCILE_REASON_RETRY_EXHAUSTED = "reconcile_retry_exhausted"
RECONCILE_REASON_NON_RETRYABLE_ERROR = "reconcile_non_retryable_error"
RECONCILE_REASON_IN_PROGRESS = "reconcile_in_progress"

RECONCILE_REASON_CODES = (
    RECONCILE_REASON_RETRY_EXHAUSTED,
    RECONCILE_REASON_NON_RETRYABLE_ERROR,
    RECONCILE_REASON_IN_PROGRESS,
)
