from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..contracts import EventEnvelope


@dataclass(frozen=True)
class SourceCursor:
    value: str | None = None


class EventSourceAdapter(Protocol):
    name: str
    category: str

    def poll(self, cursor: SourceCursor) -> tuple[list[EventEnvelope], SourceCursor]:
        ...

