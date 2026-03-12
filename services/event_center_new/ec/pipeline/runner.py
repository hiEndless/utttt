from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
import logging
from typing import Any, Protocol

from ..context.builder import ContextBuildInput, ContextBuilder
from ..contracts import EventEnvelope
from ..correlation.rules import CorrelationEngine
from .stages import EvidenceExtractor, FinalGate, FinalGateInput, L0Processor, L1Aggregator, Normalizer
from ..sources.base import EventSourceAdapter, SourceCursor
from ..storage.memory import EventMemory, MemoryPut

logger = logging.getLogger(__name__)


class LayerStore(Protocol):
    def write_raw(self, payload: dict[str, Any]) -> None:
        ...

    def write_normalized(self, payload: dict[str, Any]) -> None:
        ...

    def write_evidence(self, payload: dict[str, Any]) -> None:
        ...

    def write_context(self, payload: dict[str, Any]) -> None:
        ...

    def write_selected(self, payload: dict[str, Any]) -> None:
        ...


@dataclass(frozen=True)
class RunnerHealthSnapshot:
    heartbeat: int
    last_run_ms: int
    run_count: int
    error_count: int
    last_error: str


class EventPipelineRunner:
    """最小可运行事件流水线。"""

    def __init__(
        self,
        *,
        sources: list[EventSourceAdapter],
        normalizer: Normalizer,
        extractor: EvidenceExtractor,
        correlation_engine: CorrelationEngine,
        context_builder: ContextBuilder,
        l0_processor: L0Processor,
        l1_aggregator: L1Aggregator,
        final_gate: FinalGate,
        event_memory: EventMemory,
        layer_store: LayerStore,
    ) -> None:
        self._sources = list(sources)
        self._normalizer = normalizer
        self._extractor = extractor
        self._correlation_engine = correlation_engine
        self._context_builder = context_builder
        self._l0_processor = l0_processor
        self._l1_aggregator = l1_aggregator
        self._final_gate = final_gate
        self._event_memory = event_memory
        self._layer_store = layer_store
        self._cursors: dict[str, SourceCursor] = {src.name: SourceCursor() for src in self._sources}
        self._heartbeat = 0
        self._last_run_ms = 0
        self._run_count = 0
        self._error_count = 0
        self._last_error = ""

    def run_once(self, *, stop_on_error: bool = False) -> list[dict[str, Any]]:
        """执行一轮拉取并返回本轮 selected 输出。"""

        import time

        self._heartbeat += 1
        self._run_count += 1
        self._last_run_ms = int(time.time() * 1000)
        selected_out: list[dict[str, Any]] = []
        for src in self._sources:
            cursor = self._cursors.get(src.name, SourceCursor())
            events, next_cursor = src.poll(cursor)
            self._cursors[src.name] = next_cursor
            if not events:
                logger.debug("事件中心轮询无新事件 source=%s", src.name)
                continue
            logger.info("事件中心轮询到新事件 source=%s count=%s", src.name, len(events))
            for ev in events:
                try:
                    selected = self._process_event(ev)
                    if selected is not None:
                        payload = asdict(selected)
                        self._layer_store.write_selected(payload)
                        selected_out.append(payload)
                except Exception as exc:  # noqa: BLE001
                    # 中文注释：单事件处理失败不阻断整轮轮询，计入健康状态便于监控告警。
                    self._error_count += 1
                    self._last_error = f"{type(exc).__name__}: {exc}"
                    logger.exception("事件处理失败 source=%s event_id=%s", src.name, getattr(ev, "id", ""))
                    if stop_on_error:
                        raise
        return selected_out

    def health_snapshot(self) -> RunnerHealthSnapshot:
        return RunnerHealthSnapshot(
            heartbeat=self._heartbeat,
            last_run_ms=self._last_run_ms,
            run_count=self._run_count,
            error_count=self._error_count,
            last_error=self._last_error,
        )

    def _process_event(self, event: EventEnvelope):  # type: ignore[no-untyped-def]
        self._layer_store.write_raw(asdict(event))
        normalized = self._normalizer.normalize(event)
        self._layer_store.write_normalized(asdict(normalized))

        new_evidences = self._extractor.extract(normalized)
        for ev in new_evidences:
            self._layer_store.write_evidence(asdict(ev))

        self._event_memory.put(MemoryPut(event=normalized, evidences=new_evidences))
        active = self._event_memory.get_active_evidences(asset=normalized.asset, ts_ms=normalized.ts_ms)
        merged = self._correlation_engine.correlate(active)
        ctx = self._context_builder.build(
            ContextBuildInput(
                ts_ms=normalized.ts_ms,
                asset=normalized.asset,
                evidences=merged,
            )
        )
        self._layer_store.write_context(asdict(ctx))
        l0 = self._l0_processor.process(ctx)
        l1 = self._l1_aggregator.aggregate(ctx, l0)
        selected = self._final_gate.emit(
            FinalGateInput(
                context=ctx,
                l0=l0,
                l1=l1,
                trigger_event=normalized,
            )
        )
        return selected
