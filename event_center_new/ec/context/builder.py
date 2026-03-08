from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..contracts import EventContextSnapshot, Evidence


@dataclass(frozen=True)
class ContextBuildInput:
    ts_ms: int
    asset: str
    evidences: list[Evidence]
    last_context: EventContextSnapshot | None = None


class ContextBuilder(Protocol):
    def build(self, inp: ContextBuildInput) -> EventContextSnapshot:
        ...
