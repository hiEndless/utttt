from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..contracts import (
    Evidence,
    EventEnvelope,
    EventContextSnapshot,
    ClassifiedEvent,
    PrioritizedEvent,
    SelectedEvent,
)


class Normalizer(Protocol):
    def normalize(self, event: EventEnvelope) -> EventEnvelope:
        ...


class EvidenceExtractor(Protocol):
    def extract(self, event: EventEnvelope) -> list[Evidence]:
        ...


@dataclass(frozen=True)
class ContextInput:
    ts_ms: int
    asset: str
    evidences: list[Evidence]
    last_context: EventContextSnapshot | None = None


class L0Processor(Protocol):
    def process(self, context: EventContextSnapshot) -> ClassifiedEvent:
        ...


class L1Aggregator(Protocol):
    def aggregate(self, context: EventContextSnapshot, l0: ClassifiedEvent | None) -> PrioritizedEvent:
        ...


@dataclass(frozen=True)
class FinalGateInput:
    context: EventContextSnapshot
    l0: ClassifiedEvent | None
    l1: PrioritizedEvent | None
    trigger_event: EventEnvelope | None = None
    extra: dict[str, Any] | None = None


class FinalGate(Protocol):
    def emit(self, inp: FinalGateInput) -> SelectedEvent | None:
        ...
