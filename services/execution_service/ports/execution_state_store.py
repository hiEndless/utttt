from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


class ExecutionStateStore(Protocol):
    """执行状态存储端口：按 decision_id 读写状态机快照。"""

    async def get_state(self, decision_id: str) -> Optional[Dict[str, Any]]:
        ...

    async def save_state(self, decision_id: str, state: Dict[str, Any]) -> None:
        ...
