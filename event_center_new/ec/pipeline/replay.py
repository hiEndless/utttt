from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any

from ..contracts import EventEnvelope, EventSource, EventTrace
from ..context.builder import ContextBuilder
from ..correlation.rules import CorrelationEngine
from ..sources.memory import InMemoryEventSource
from ..storage.memory import EventMemory, InMemoryLayerStore
from .runner import EventPipelineRunner
from .stages import EvidenceExtractor, FinalGate, L0Processor, L1Aggregator, Normalizer


@dataclass(frozen=True)
class ReplayResult:
    selected: list[dict[str, Any]]
    raw_count: int
    normalized_count: int
    evidence_count: int
    context_count: int
    selected_count: int


class EventReplayTool:
    """最小重放工具：给定事件输入，重放并返回分层产物统计。"""

    def __init__(
        self,
        *,
        normalizer: Normalizer,
        extractor: EvidenceExtractor,
        correlation_engine: CorrelationEngine,
        context_builder: ContextBuilder,
        l0_processor: L0Processor,
        l1_aggregator: L1Aggregator,
        final_gate: FinalGate,
        event_memory: EventMemory,
    ) -> None:
        self._normalizer = normalizer
        self._extractor = extractor
        self._correlation_engine = correlation_engine
        self._context_builder = context_builder
        self._l0_processor = l0_processor
        self._l1_aggregator = l1_aggregator
        self._final_gate = final_gate
        self._event_memory = event_memory

    def replay(self, events: list[EventEnvelope]) -> ReplayResult:
        store = InMemoryLayerStore()
        runner = EventPipelineRunner(
            sources=[InMemoryEventSource(name="replay_source", category="replay", events=list(events))],
            normalizer=self._normalizer,
            extractor=self._extractor,
            correlation_engine=self._correlation_engine,
            context_builder=self._context_builder,
            l0_processor=self._l0_processor,
            l1_aggregator=self._l1_aggregator,
            final_gate=self._final_gate,
            event_memory=self._event_memory,
            layer_store=store,
        )
        selected = runner.run_once()
        return ReplayResult(
            selected=selected,
            raw_count=len(store.raw),
            normalized_count=len(store.normalized),
            evidence_count=len(store.evidence),
            context_count=len(store.context),
            selected_count=len(store.selected),
        )

    def replay_from_dicts(self, raw_events: list[dict[str, Any]]) -> ReplayResult:
        events = [event_from_dict(item) for item in raw_events]
        return self.replay(events)


def event_from_dict(payload: dict[str, Any]) -> EventEnvelope:
    source_raw = payload.get("source")
    trace_raw = payload.get("trace")
    source = EventSource(
        name=str((source_raw or {}).get("name") or ""),
        category=str((source_raw or {}).get("category") or ""),
    )
    trace = EventTrace(
        dedup_key=(trace_raw or {}).get("dedup_key"),
        correlation_id=(trace_raw or {}).get("correlation_id"),
        parent_id=(trace_raw or {}).get("parent_id"),
        produced_by=(trace_raw or {}).get("produced_by"),
        schema_version=(trace_raw or {}).get("schema_version"),
    )
    return EventEnvelope(
        id=str(payload.get("id") or ""),
        ts_ms=int(payload.get("ts_ms") or 0),
        exchange=(None if payload.get("exchange") is None else str(payload.get("exchange"))),
        account_id=(None if payload.get("account_id") is None else str(payload.get("account_id"))),
        asset=str(payload.get("asset") or ""),
        kind=str(payload.get("kind") or "tactical"),  # type: ignore[arg-type]
        type=str(payload.get("type") or ""),
        source=source,
        importance=float(payload.get("importance") or 0.0),
        ttl_ms=int(payload.get("ttl_ms") or 0),
        payload=dict(payload.get("payload") or {}),
        meta=dict(payload.get("meta") or {}),
        trace=trace,
    )


def diff_selected(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> list[str]:
    """比较两轮 selected 结果差异，返回差异描述列表。"""

    def _normalize(items: list[dict[str, Any]]) -> list[str]:
        return sorted(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in items)

    aa = _normalize(a)
    bb = _normalize(b)
    if aa == bb:
        return []
    diffs: list[str] = []
    sa, sb = set(aa), set(bb)
    for item in sorted(sa - sb):
        diffs.append(f"-only_in_a: {item}")
    for item in sorted(sb - sa):
        diffs.append(f"-only_in_b: {item}")
    return diffs


def event_to_dict(event: EventEnvelope) -> dict[str, Any]:
    return asdict(event)
