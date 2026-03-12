from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..contracts import EventContextSnapshot, Evidence
from .buckets import BucketTopKPolicy, bucket_by_horizon, select_top_k_by_bucket
from ..prioritization.scorer import PriorityScorer


@dataclass(frozen=True)
class ContextBuildInput:
    ts_ms: int
    asset: str
    evidences: list[Evidence]
    last_context: EventContextSnapshot | None = None


class ContextBuilder(Protocol):
    def build(self, inp: ContextBuildInput) -> EventContextSnapshot:
        ...


@dataclass(frozen=True)
class DefaultContextBuilderConfig:
    top_k_policy: BucketTopKPolicy = BucketTopKPolicy()


class DefaultContextBuilder:
    """默认上下文构建器：按评分做分桶 Top-K 并输出冲突摘要。"""

    def __init__(self, cfg: DefaultContextBuilderConfig | None = None, scorer: PriorityScorer | None = None) -> None:
        self._cfg = cfg or DefaultContextBuilderConfig()
        self._scorer = scorer or PriorityScorer()

    def build(self, inp: ContextBuildInput) -> EventContextSnapshot:
        evidences = list(inp.evidences or [])
        scored = {id(e): self._scorer.score_evidence(e, now_ms=inp.ts_ms) for e in evidences}
        buckets = bucket_by_horizon(evidences)
        key_evidences = select_top_k_by_bucket(buckets=buckets, scored=scored, policy=self._cfg.top_k_policy)
        conflicts = _build_conflicts(evidences)
        tags = _build_tags(evidences=evidences, conflicts=conflicts)
        active_triggers = _build_active_triggers(evidences)
        return EventContextSnapshot(
            ts_ms=inp.ts_ms,
            asset=inp.asset,
            key_evidences=key_evidences,
            active_triggers=active_triggers,
            conflicts=conflicts,
            tags=tags,
        )


def _build_conflicts(evidences: list[Evidence]) -> list[dict[str, str]]:
    by_type: dict[str, set[str]] = {}
    for ev in evidences:
        d = str(ev.direction)
        if d not in {"bullish", "bearish"}:
            continue
        by_type.setdefault(ev.type, set()).add(d)
    out: list[dict[str, str]] = []
    for ev_type, dirs in by_type.items():
        if len(dirs) >= 2:
            out.append({"type": ev_type, "conflict": "bullish_vs_bearish"})
    return out


def _build_tags(evidences: list[Evidence], conflicts: list[dict[str, str]]) -> list[str]:
    tags: set[str] = set()
    if conflicts:
        tags.add("has_conflict")
    for ev in evidences:
        if ev.horizon == "short":
            tags.add("has_short_horizon")
        if ev.horizon == "mid":
            tags.add("has_mid_horizon")
        if ev.horizon == "long":
            tags.add("has_long_horizon")
    return sorted(tags)


def _build_active_triggers(evidences: list[Evidence]) -> list[dict[str, str | int]]:
    out: list[dict[str, str | int]] = []
    for ev in sorted(evidences, key=lambda x: x.ts_ms, reverse=True)[:5]:
        out.append({"type": ev.type, "direction": ev.direction, "ts_ms": ev.ts_ms})
    return out
