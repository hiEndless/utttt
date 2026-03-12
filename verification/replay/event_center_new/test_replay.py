from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys
import time

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.event_center_new.ec.context.builder import DefaultContextBuilder
from services.event_center_new.ec.contracts import EventEnvelope, EventSource
from services.event_center_new.ec.correlation.rules import CorrelationEngine
from services.event_center_new.ec.pipeline.defaults import (
    DeterministicFinalGate,
    HeuristicL0Processor,
    HeuristicL1Aggregator,
    PassThroughNormalizer,
    PayloadEvidenceExtractor,
)
from services.event_center_new.ec.pipeline.replay import EventReplayTool, diff_selected, event_from_dict
from services.event_center_new.ec.storage.memory import InMemoryEventMemory


def _build_tool() -> EventReplayTool:
    return EventReplayTool(
        normalizer=PassThroughNormalizer(),
        extractor=PayloadEvidenceExtractor(),
        correlation_engine=CorrelationEngine(rules=[]),
        context_builder=DefaultContextBuilder(),
        l0_processor=HeuristicL0Processor(),
        l1_aggregator=HeuristicL1Aggregator(),
        final_gate=DeterministicFinalGate(),
        event_memory=InMemoryEventMemory(),
    )


def _sample_event() -> EventEnvelope:
    now_ms = int(time.time() * 1000)
    return EventEnvelope(
        id="r-1",
        ts_ms=now_ms,
        asset="ETHUSDT",
        kind="tactical",
        type="technical.indicator_signal",
        source=EventSource(name="feature_service", category="technical"),
        importance=0.8,
        ttl_ms=600000,
        payload={
            "evidences": [
                {"type": "a", "direction": "bullish", "strength": 0.7, "horizon": "short", "importance": 0.8},
                {"type": "b", "direction": "bullish", "strength": 0.6, "horizon": "short", "importance": 0.7},
            ]
        },
    )


def test_replay_deterministic_no_diff() -> None:
    tool1 = _build_tool()
    tool2 = _build_tool()
    event = _sample_event()
    res1 = tool1.replay([event])
    res2 = tool2.replay([event])
    assert res1.selected_count == 1
    assert res2.selected_count == 1
    assert diff_selected(res1.selected, res2.selected) == []


def test_replay_from_dict_roundtrip() -> None:
    tool = _build_tool()
    event = _sample_event()
    raw = asdict(event)
    parsed = event_from_dict(raw)
    assert parsed.id == event.id
    res = tool.replay_from_dicts([raw])
    assert res.raw_count == 1
    assert res.normalized_count == 1
