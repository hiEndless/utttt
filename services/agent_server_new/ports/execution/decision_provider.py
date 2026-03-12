from __future__ import annotations

from typing import Any, Dict, Protocol


class ExecutionDecisionProvider(Protocol):
    """执行裁决端口：把 agent 意图提交给 execution_service。"""

    async def decide(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ...
