from __future__ import annotations

from pathlib import Path
import sys
import time

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from event_center_new.ec.context.builder import DefaultContextBuilder
from event_center_new.ec.contracts import EventEnvelope, EventSource
from event_center_new.ec.correlation.rules import CorrelationEngine
from event_center_new.ec.pipeline.defaults import (
    DeterministicFinalGate,
    HeuristicL0Processor,
    HeuristicL1Aggregator,
    PassThroughNormalizer,
    PayloadEvidenceExtractor,
    SelectPolicyConfig,
)
from event_center_new.ec.pipeline.runner import EventPipelineRunner
from event_center_new.ec.sources.memory import InMemoryEventSource
from event_center_new.ec.storage.memory import InMemoryEventMemory, InMemoryLayerStore


class _BoomExtractor(PayloadEvidenceExtractor):
    def extract(self, event: EventEnvelope):  # type: ignore[override]
        raise RuntimeError(f"boom:{event.id}")


def _build_runner(events: list[EventEnvelope], *, mixed_min_score: float = 0.25) -> tuple[EventPipelineRunner, InMemoryLayerStore]:
    source = InMemoryEventSource(name="test_source", category="test", events=events)
    store = InMemoryLayerStore()
    runner = EventPipelineRunner(
        sources=[source],
        normalizer=PassThroughNormalizer(),
        extractor=PayloadEvidenceExtractor(),
        correlation_engine=CorrelationEngine(rules=[]),
        context_builder=DefaultContextBuilder(),
        l0_processor=HeuristicL0Processor(),
        l1_aggregator=HeuristicL1Aggregator(),
        final_gate=DeterministicFinalGate(cfg=SelectPolicyConfig(mixed_min_score=mixed_min_score)),
        event_memory=InMemoryEventMemory(),
        layer_store=store,
    )
    return runner, store


def test_runner_end_to_end_bullish_selected() -> None:
    now_ms = int(time.time() * 1000)
    event = EventEnvelope(
        id="evt-1",
        ts_ms=now_ms,
        asset="ETHUSDT",
        kind="tactical",
        type="technical.indicator_signal",
        source=EventSource(name="feature_service", category="technical"),
        importance=0.9,
        ttl_ms=600000,
        payload={
            "evidences": [
                {"type": "a", "direction": "bullish", "strength": 0.8, "horizon": "short", "importance": 0.8},
                {"type": "b", "direction": "bullish", "strength": 0.7, "horizon": "short", "importance": 0.8},
            ]
        },
    )
    runner, store = _build_runner([event])
    selected = runner.run_once()
    assert len(selected) == 1
    out = selected[0]
    assert out["asset"] == "ETHUSDT"
    assert out["direction_hint"] in {"bullish", "mixed"}
    assert isinstance(out["context_snapshot"]["key_evidences"], list)
    assert len(store.raw) == 1
    assert len(store.normalized) == 1
    assert len(store.evidence) == 2
    assert len(store.context) == 1
    assert len(store.selected) == 1


def test_runner_mixed_noise_can_be_dropped() -> None:
    now_ms = int(time.time() * 1000)
    event = EventEnvelope(
        id="evt-2",
        ts_ms=now_ms,
        asset="ETHUSDT",
        kind="tactical",
        type="technical.indicator_signal",
        source=EventSource(name="feature_service", category="technical"),
        importance=0.4,
        ttl_ms=600000,
        payload={
            "evidences": [
                {"type": "a", "direction": "bullish", "strength": 0.1, "horizon": "short", "importance": 0.2},
                {"type": "b", "direction": "bearish", "strength": 0.1, "horizon": "short", "importance": 0.2},
            ]
        },
    )
    runner, _store = _build_runner([event], mixed_min_score=0.3)
    selected = runner.run_once()
    assert selected == []


def test_runner_health_snapshot_updates_after_run() -> None:
    now_ms = int(time.time() * 1000)
    event = EventEnvelope(
        id="evt-health-1",
        ts_ms=now_ms,
        asset="ETHUSDT",
        kind="tactical",
        type="technical.indicator_signal",
        source=EventSource(name="feature_service", category="technical"),
        importance=0.9,
        ttl_ms=600000,
        payload={"evidences": [{"type": "a", "direction": "bullish", "strength": 0.8, "horizon": "short", "importance": 0.8}]},
    )
    runner, _store = _build_runner([event])
    before = runner.health_snapshot()
    assert before.heartbeat == 0
    assert before.run_count == 0
    assert before.error_count == 0
    assert before.last_run_ms == 0
    runner.run_once()
    after = runner.health_snapshot()
    assert after.heartbeat == 1
    assert after.run_count == 1
    assert after.error_count == 0
    assert after.last_run_ms >= now_ms


def test_runner_health_counts_event_errors_without_stopping() -> None:
    now_ms = int(time.time() * 1000)
    event = EventEnvelope(
        id="evt-health-err",
        ts_ms=now_ms,
        asset="ETHUSDT",
        kind="tactical",
        type="technical.indicator_signal",
        source=EventSource(name="feature_service", category="technical"),
        importance=0.9,
        ttl_ms=600000,
        payload={"evidences": [{"type": "a", "direction": "bullish", "strength": 0.8, "horizon": "short", "importance": 0.8}]},
    )
    source = InMemoryEventSource(name="test_source", category="test", events=[event])
    store = InMemoryLayerStore()
    runner = EventPipelineRunner(
        sources=[source],
        normalizer=PassThroughNormalizer(),
        extractor=_BoomExtractor(),
        correlation_engine=CorrelationEngine(rules=[]),
        context_builder=DefaultContextBuilder(),
        l0_processor=HeuristicL0Processor(),
        l1_aggregator=HeuristicL1Aggregator(),
        final_gate=DeterministicFinalGate(cfg=SelectPolicyConfig()),
        event_memory=InMemoryEventMemory(),
        layer_store=store,
    )
    selected = runner.run_once()
    assert selected == []
    health = runner.health_snapshot()
    assert health.run_count == 1
    assert health.error_count == 1
    assert "boom:evt-health-err" in health.last_error
