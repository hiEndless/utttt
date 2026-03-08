from __future__ import annotations

import math
from dataclasses import dataclass

from ..contracts import Evidence


@dataclass(frozen=True)
class RecencyDecay:
    half_life_ms: int

    def factor(self, now_ms: int, event_ts_ms: int) -> float:
        age_ms = max(0, now_ms - event_ts_ms)
        if self.half_life_ms <= 0:
            return 1.0
        return math.exp(-math.log(2) * (age_ms / float(self.half_life_ms)))


@dataclass(frozen=True)
class PriorityScorerConfig:
    recency_decay: RecencyDecay = RecencyDecay(half_life_ms=15 * 60 * 1000)
    min_confidence: float = 0.2


class PriorityScorer:
    def __init__(self, cfg: PriorityScorerConfig | None = None) -> None:
        self._cfg = cfg or PriorityScorerConfig()

    def score_evidence(self, evidence: Evidence, now_ms: int) -> float:
        confidence = evidence.confidence if evidence.confidence is not None else 1.0
        confidence = max(self._cfg.min_confidence, min(1.0, confidence))

        importance = max(0.0, min(1.0, evidence.importance))
        strength = max(0.0, min(1.0, evidence.strength))
        recency = self._cfg.recency_decay.factor(now_ms=now_ms, event_ts_ms=evidence.ts_ms)

        return importance * strength * confidence * recency

