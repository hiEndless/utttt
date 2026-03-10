from __future__ import annotations

from dataclasses import dataclass

from ..contracts import EventEnvelope
from .base import SourceCursor


@dataclass
class InMemoryEventSource:
    name: str
    category: str
    events: list[EventEnvelope]

    def poll(self, cursor: SourceCursor) -> tuple[list[EventEnvelope], SourceCursor]:
        offset = int(cursor.value or "0")
        if offset >= len(self.events):
            return [], SourceCursor(value=str(offset))
        out = self.events[offset:]
        return out, SourceCursor(value=str(len(self.events)))
