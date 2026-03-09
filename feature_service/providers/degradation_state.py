from __future__ import annotations

from contextvars import ContextVar
from typing import List

# 使用 ContextVar 维护“单次请求”的降级原因。
# 注意：在 gather 并发子任务中，Context 会复制；这里存可变 list 并就地 append，确保父任务可见。
_DEGRADED_REASONS: ContextVar[List[str]] = ContextVar("_DEGRADED_REASONS", default=[])


def reset_degradation_state() -> None:
    _DEGRADED_REASONS.set([])


def mark_degraded(reason: str) -> None:
    reason_norm = str(reason or "").strip()
    if not reason_norm:
        return
    current = _DEGRADED_REASONS.get()
    if reason_norm in current:
        return
    current.append(reason_norm)


def snapshot_degradation_reasons() -> List[str]:
    return list(_DEGRADED_REASONS.get())
