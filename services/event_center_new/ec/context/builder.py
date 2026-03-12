from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from contracts.schemas.alternative_source_summary_contract import (
    get_alternative_source_names,
    get_alternative_source_required_keys,
)
from contracts.semantic_policies.source_semantics import (
    get_event_center_data_source,
    get_event_center_inference_source,
    get_event_center_empty_provider_state,
    get_event_center_present_provider_state,
)
from ..contracts import EventContextSnapshot, Evidence
from .buckets import BucketTopKPolicy, bucket_by_horizon, select_top_k_by_bucket
from ..prioritization.scorer import PriorityScorer

_ALT_SOURCE_NAMES = get_alternative_source_names()
_ALT_SUMMARY_REQUIRED_KEYS = set(get_alternative_source_required_keys())


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
        alternative_sources_summary = _build_alternative_sources_summary(evidences)
        return EventContextSnapshot(
            ts_ms=inp.ts_ms,
            asset=inp.asset,
            key_evidences=key_evidences,
            active_triggers=active_triggers,
            conflicts=conflicts,
            tags=tags,
            alternative_sources_summary=alternative_sources_summary,
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


def _detect_alternative_source(ev: Evidence) -> str | None:
    attrs = dict(ev.attrs or {})
    explicit = str(attrs.get("source_type") or "").strip().lower()
    if explicit in set(_ALT_SOURCE_NAMES):
        return explicit

    category = str(attrs.get("source_category") or "").strip().lower()
    if category in {"news", "macro_news"}:
        return "news"
    if category in {"social", "sentiment_social"}:
        return "social"
    if category in {"onchain", "chain"}:
        return "onchain"

    source_name = str(attrs.get("source_name") or attrs.get("source") or "").strip().lower()
    if source_name:
        if any(token in source_name for token in {"twitter", "x_", "reddit", "discord", "telegram"}):
            return "social"
        if any(token in source_name for token in {"glassnode", "nansen", "chainalysis", "arkham", "onchain"}):
            return "onchain"
        if any(token in source_name for token in {"coindesk", "cointelegraph", "bloomberg", "reuters", "news"}):
            return "news"

    text = f"{ev.type} {category} {source_name}".lower()
    if "onchain" in text:
        return "onchain"
    if "social" in text or "twitter" in text:
        return "social"
    if "news" in text or "macro" in text:
        return "news"
    return None


def _build_alternative_sources_summary(evidences: list[Evidence]) -> dict[str, object]:
    source_names = _ALT_SOURCE_NAMES
    present_provider_state = get_event_center_present_provider_state()
    empty_provider_state = get_event_center_empty_provider_state()
    feature_keys: dict[str, set[str]] = {name: set() for name in source_names}
    counts: dict[str, int] = {name: 0 for name in source_names}
    data_sources: dict[str, str] = {name: get_event_center_data_source(name) for name in source_names}
    inference_sources: dict[str, str] = {name: get_event_center_inference_source() for name in source_names}

    for ev in evidences:
        src = _detect_alternative_source(ev)
        if src is None:
            continue
        counts[src] += 1
        attrs = dict(ev.attrs or {})
        raw_data_source = str(
            attrs.get("data_source")
            or attrs.get("source_name")
            or attrs.get("source")
            or ""
        ).strip()
        if raw_data_source:
            data_sources[src] = raw_data_source
        raw_inference_source = str(
            attrs.get("inference_source")
            or attrs.get("produced_by")
            or ""
        ).strip()
        if raw_inference_source:
            inference_sources[src] = raw_inference_source
        for k in attrs.keys():
            key = str(k or "").strip()
            if key:
                feature_keys[src].add(key)

    available_sources = [name for name in source_names if counts[name] > 0]
    unavailable_sources = [name for name in source_names if counts[name] == 0]
    provider_states = {name: (present_provider_state if counts[name] > 0 else empty_provider_state) for name in source_names}

    out = {
        "available_sources": available_sources,
        "unavailable_sources": unavailable_sources,
        "provider_states": provider_states,
        "data_sources": data_sources,
        "inference_sources": inference_sources,
        "feature_keys": {name: sorted(feature_keys[name]) for name in source_names},
        "evidence_counts": counts,
    }
    if not _ALT_SUMMARY_REQUIRED_KEYS.issubset(set(out.keys())):
        return {}
    return out
