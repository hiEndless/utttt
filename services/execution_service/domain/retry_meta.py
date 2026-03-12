from __future__ import annotations

# 中文注释：submit/reconcile 共享重试元信息状态枚举。
RETRY_META_STATUS_OK = "ok"
RETRY_META_STATUS_FAILED = "failed"

RETRY_META_STATUSES = (
    RETRY_META_STATUS_OK,
    RETRY_META_STATUS_FAILED,
)
