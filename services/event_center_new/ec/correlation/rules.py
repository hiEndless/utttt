from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..contracts import Direction, Evidence, Horizon


@dataclass(frozen=True)
class CorrelationResult:
    synthesized: list[Evidence]
    suppressed_types: set[str]


class CorrelationRule(Protocol):
    def apply(self, evidences: list[Evidence]) -> CorrelationResult:
        ...


@dataclass(frozen=True)
class SimpleClusterRule:
    a_type: str
    b_type: str
    out_type: str
    out_direction: Direction
    out_horizon: Horizon
    suppress_inputs: bool = False

    def apply(self, evidences: list[Evidence]) -> CorrelationResult:
        a = [e for e in evidences if e.type == self.a_type]
        b = [e for e in evidences if e.type == self.b_type]

        if not a or not b:
            return CorrelationResult(synthesized=[], suppressed_types=set())

        def best(items: list[Evidence]) -> Evidence:
            return max(items, key=lambda x: (x.strength, x.importance, x.confidence or 1.0))

        ea = best(a)
        eb = best(b)

        synthesized = Evidence(
            ts_ms=max(ea.ts_ms, eb.ts_ms),
            type=self.out_type,
            direction=self.out_direction,
            strength=min(1.0, (ea.strength + eb.strength) / 2.0),
            horizon=self.out_horizon,
            ttl_ms=min(ea.ttl_ms, eb.ttl_ms),
            importance=min(1.0, max(ea.importance, eb.importance)),
            confidence=min(1.0, ((ea.confidence or 1.0) + (eb.confidence or 1.0)) / 2.0),
            source_refs=[
                {"type": ea.type, "ts_ms": ea.ts_ms},
                {"type": eb.type, "ts_ms": eb.ts_ms},
            ],
            attrs={"cluster": True},
        )

        suppressed = {self.a_type, self.b_type} if self.suppress_inputs else set()
        return CorrelationResult(synthesized=[synthesized], suppressed_types=suppressed)


class CorrelationEngine:
    def __init__(self, rules: list[CorrelationRule]) -> None:
        self._rules = rules

    def correlate(self, evidences: list[Evidence]) -> list[Evidence]:
        synthesized: list[Evidence] = []
        suppressed_types: set[str] = set()

        for rule in self._rules:
            res = rule.apply([e for e in evidences if e.type not in suppressed_types])
            synthesized.extend(res.synthesized)
            suppressed_types |= res.suppressed_types

        remaining = [e for e in evidences if e.type not in suppressed_types]
        return remaining + synthesized

