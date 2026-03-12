from __future__ import annotations

from typing import Any, Dict, Protocol

from services.execution_service.domain.contracts import DecisionIntent


class ExecutionSink(Protocol):
    """执行下沉端口：可对接交易所或模拟执行器。"""

    async def submit(self, decision: DecisionIntent, execution_action: str) -> Dict[str, Any]:
        ...
