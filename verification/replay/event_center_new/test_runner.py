from __future__ import annotations

from pathlib import Path
import sys
import time

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.event_center_new.ec.context.builder import DefaultContextBuilder
from services.event_center_new.ec.contracts import EventContextSnapshot, EventEnvelope, EventSource
from services.event_center_new.ec.correlation.rules import CorrelationEngine
from services.event_center_new.ec.pipeline.defaults import (
    DeterministicFinalGate,
    HeuristicL0Processor,
    HeuristicL1Aggregator,
    PassThroughNormalizer,
    PayloadEvidenceExtractor,
    SelectPolicyConfig,
)
from services.event_center_new.ec.pipeline.runner import EventPipelineRunner
from services.event_center_new.ec.sources.memory import InMemoryEventSource
from services.event_center_new.ec.storage.memory import InMemoryEventMemory, InMemoryLayerStore


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
    assert dict(out.get("source") or {}).get("name") == "feature_service"
    assert "schema_version" in set(dict(out.get("trace") or {}).keys())
    assert isinstance(out["context_snapshot"]["key_evidences"], list)
    alt = dict(out["context_snapshot"].get("alternative_sources_summary") or {})
    assert set(alt.keys()) >= {
        "available_sources",
        "unavailable_sources",
        "provider_states",
        "data_sources",
        "inference_sources",
        "feature_keys",
        "evidence_counts",
    }
    assert len(store.raw) == 1
    assert len(store.normalized) == 1
    assert len(store.evidence) == 2
    assert len(store.context) == 1
    assert len(store.selected) == 1


def test_runner_builds_alternative_source_summary_from_evidences() -> None:
    now_ms = int(time.time() * 1000)
    event = EventEnvelope(
        id="evt-alt-1",
        ts_ms=now_ms,
        asset="ETHUSDT",
        kind="tactical",
        type="news.regulatory",
        source=EventSource(name="news_feed", category="news"),
        importance=0.9,
        ttl_ms=600000,
        payload={
            "evidences": [
                {"type": "news.regulatory", "direction": "mixed", "strength": 0.5, "horizon": "mid", "importance": 0.7, "attrs": {"headline_score": 0.8}},
                {"type": "onchain.exchange_inflow", "direction": "bearish", "strength": 0.6, "horizon": "short", "importance": 0.8, "attrs": {"inflow_usd": 100}},
            ]
        },
    )
    runner, _store = _build_runner([event])
    selected = runner.run_once()
    assert len(selected) == 1
    alt = dict(selected[0]["context_snapshot"].get("alternative_sources_summary") or {})
    assert "news" in list(alt.get("available_sources") or [])
    assert "onchain" in list(alt.get("available_sources") or [])
    assert alt.get("provider_states", {}).get("social") == "empty"
    assert alt.get("data_sources", {}).get("news") == "event_center_new.news"
    assert alt.get("inference_sources", {}).get("news") == "event_center_new.selector"


def test_runner_alternative_source_summary_uses_attrs_source_semantics() -> None:
    now_ms = int(time.time() * 1000)
    event = EventEnvelope(
        id="evt-alt-2",
        ts_ms=now_ms,
        asset="ETHUSDT",
        kind="tactical",
        type="news.macro",
        source=EventSource(name="news_feed", category="news"),
        importance=0.9,
        ttl_ms=600000,
        payload={
            "evidences": [
                {
                    "type": "news.macro",
                    "direction": "bullish",
                    "strength": 0.5,
                    "horizon": "mid",
                    "importance": 0.7,
                    "attrs": {
                        "source_category": "news",
                        "source_name": "coindesk",
                        "produced_by": "event_center_new.news_parser",
                    },
                }
            ]
        },
    )
    runner, _store = _build_runner([event])
    selected = runner.run_once()
    assert len(selected) == 1
    alt = dict(selected[0]["context_snapshot"].get("alternative_sources_summary") or {})
    assert alt.get("data_sources", {}).get("news") == "coindesk"
    assert alt.get("inference_sources", {}).get("news") == "event_center_new.news_parser"


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


def test_extractor_and_l0_expose_explicit_confidence_semantics() -> None:
    now_ms = int(time.time() * 1000)
    event = EventEnvelope(
        id="evt-conf-1",
        ts_ms=now_ms,
        asset="ETHUSDT",
        kind="tactical",
        type="technical.indicator_signal",
        source=EventSource(name="feature_service", category="technical"),
        importance=0.9,
        ttl_ms=600000,
        payload={
            "evidences": [
                {
                    "type": "a",
                    "direction": "bullish",
                    "strength": 0.8,
                    "horizon": "short",
                    "importance": 0.7,
                    "evidence_confidence": 0.9,
                },
                {
                    "type": "b",
                    "direction": "bearish",
                    "strength": 0.3,
                    "horizon": "short",
                    "importance": 0.6,
                    "confidence": 0.4,
                },
            ]
        },
    )
    runner, store = _build_runner([event])
    selected = runner.run_once()
    assert len(selected) == 1
    ev0 = store.evidence[0]
    ev1 = store.evidence[1]
    assert ev0["evidence_confidence"] == 0.9
    assert ev0["confidence"] == 0.9
    assert ev1["evidence_confidence"] == 0.4
    assert ev1["confidence"] == 0.4
    evidences = PayloadEvidenceExtractor().extract(event)
    ctx = EventContextSnapshot(ts_ms=event.ts_ms, asset=event.asset, key_evidences=evidences)
    l0 = HeuristicL0Processor().process(ctx)
    l1 = HeuristicL1Aggregator().aggregate(ctx, l0)
    assert l0.classification_confidence == l0.confidence
    assert l1.component_scores["classification_confidence"] == l0.classification_confidence


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


def test_runner_stop_on_error_raises() -> None:
    now_ms = int(time.time() * 1000)
    event = EventEnvelope(
        id="evt-health-raise",
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
        layer_store=InMemoryLayerStore(),
    )
    try:
        runner.run_once(stop_on_error=True)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "boom:evt-health-raise" in str(exc)
    health = runner.health_snapshot()
    assert health.error_count == 1
