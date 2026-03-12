from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


EventKind = Literal["strategic", "tactical", "trigger"]
Direction = Literal["bullish", "bearish", "neutral", "mixed"]
Horizon = Literal["short", "mid", "long"]
Priority = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class EventSource:
    name: str
    category: str


@dataclass(frozen=True)
class EventTrace:
    dedup_key: str | None = None
    correlation_id: str | None = None
    parent_id: str | None = None
    produced_by: str | None = None
    schema_version: str | None = None


@dataclass(frozen=True)
class EventEnvelope:
    id: str
    ts_ms: int
    asset: str
    kind: EventKind
    type: str
    source: EventSource
    importance: float
    ttl_ms: int
    payload: dict[str, Any]
    exchange: str | None = None
    account_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    trace: EventTrace = field(default_factory=EventTrace)


@dataclass(frozen=True)
class Evidence:
    ts_ms: int
    type: str
    direction: Direction
    strength: float
    horizon: Horizon
    ttl_ms: int
    importance: float
    # 显式语义字段：证据置信度（兼容保留 confidence）。
    evidence_confidence: float | None = None
    confidence: float | None = None
    source_refs: list[dict[str, Any]] = field(default_factory=list)
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventContextSnapshot:
    ts_ms: int
    asset: str
    key_evidences: list[Evidence]
    active_triggers: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClassifiedEvent:
    asset: str
    ts_ms: int
    confirmed_direction: Direction
    score: float
    confidence: float
    priority: Priority
    # 显式语义字段：分类阶段置信度（兼容保留 confidence）。
    classification_confidence: float = 0.0
    window: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PrioritizedEvent:
    asset: str
    ts_ms: int
    classification: str
    component_scores: dict[str, Any]
    key_evidences: list[Evidence]
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    routing_hints: dict[str, Any] = field(default_factory=dict)
    priority: Priority = "low"


@dataclass(frozen=True)
class SelectedEvent:
    asset: str
    ts_ms: int
    selected_type: str
    direction_hint: Direction
    priority: Priority
    context_snapshot: EventContextSnapshot
    trigger_event: EventEnvelope | None = None
    source: EventSource | None = None
    trace: EventTrace | None = None
    route: dict[str, Any] = field(default_factory=dict)
    event_ts_ms: int | None = None
    processed_ts_ms: int | None = None
