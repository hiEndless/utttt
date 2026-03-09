from __future__ import annotations

from typing import Protocol

from execution_service.domain.contracts import DecisionIntent, ExecutionResult


class ExecutionSink(Protocol):
    """执行下沉端口：可对接交易所或模拟执行器。"""

    async def submit(self, decision: DecisionIntent) -> ExecutionResult:
        ...
