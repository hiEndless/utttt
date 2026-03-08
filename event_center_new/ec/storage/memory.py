from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..contracts import Evidence, EventEnvelope


@dataclass(frozen=True)
class MemoryPut:
    event: EventEnvelope
    evidences: list[Evidence]


class EventMemory(Protocol):
    def put(self, item: MemoryPut) -> None:
        ...

    def get_active_evidences(self, asset: str, ts_ms: int) -> list[Evidence]:
        ...

