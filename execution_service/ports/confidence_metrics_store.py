from __future__ import annotations

from typing import Dict, Protocol


class ConfidenceMetricsStore(Protocol):
    async def record_decide_request(self, *, has_confidence: bool, has_decision_confidence: bool) -> None:
        ...

    async def record_mismatch_rejection(self) -> None:
        ...

    async def snapshot(self) -> Dict[str, int]:
        ...
