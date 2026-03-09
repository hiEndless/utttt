from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


class IdempotencyStore(Protocol):
    """幂等存储端口：基于 decision_id 缓存执行结果。"""

    async def get_result(self, decision_id: str) -> Optional[Dict[str, Any]]:
        ...

    async def save_result(self, decision_id: str, result: Dict[str, Any]) -> None:
        ...

    async def try_acquire_lock(self, decision_id: str, ttl_s: int) -> bool:
        ...

    async def release_lock(self, decision_id: str) -> None:
        ...
