from __future__ import annotations

import json
import logging
import os
import time

from event_center_new.ec.context.builder import DefaultContextBuilder
from event_center_new.ec.contracts import EventEnvelope, EventSource
from event_center_new.ec.correlation.rules import CorrelationEngine, SimpleClusterRule
from event_center_new.ec.pipeline.defaults import (
    DeterministicFinalGate,
    HeuristicL0Processor,
    HeuristicL1Aggregator,
    PassThroughNormalizer,
    PayloadEvidenceExtractor,
)
from event_center_new.ec.pipeline.runner import EventPipelineRunner
from event_center_new.ec.sources.memory import InMemoryEventSource
from event_center_new.ec.storage.memory import InMemoryEventMemory, InMemoryLayerStore
from event_center_new.ec.storage.redis import RedisLayerStore, RedisLayerStoreConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("event_center_new")


def _build_demo_event() -> EventEnvelope:
    now_ms = int(time.time() * 1000)
    return EventEnvelope(
        id=f"demo-{now_ms}",
        ts_ms=now_ms,
        exchange="binance",
        account_id="main",
        asset="ETHUSDT",
        kind="tactical",
        type="technical.indicator_signal",
        source=EventSource(name="feature_service", category="technical"),
        importance=0.8,
        ttl_ms=15 * 60 * 1000,
        payload={
            "evidences": [
                {
                    "type": "technical.breakout",
                    "direction": "bullish",
                    "strength": 0.7,
                    "horizon": "short",
                    "importance": 0.8,
                    "confidence": 0.75,
                },
                {
                    "type": "oi.spike",
                    "direction": "bullish",
                    "strength": 0.6,
                    "horizon": "short",
                    "importance": 0.7,
                    "confidence": 0.8,
                },
            ]
        },
    )


def main() -> None:
    source = InMemoryEventSource(
        name="demo_source",
        category="technical",
        events=[_build_demo_event()],
    )
    layer_store = _build_layer_store()
    runner = EventPipelineRunner(
        sources=[source],
        normalizer=PassThroughNormalizer(),
        extractor=PayloadEvidenceExtractor(),
        correlation_engine=CorrelationEngine(
            rules=[
                SimpleClusterRule(
                    a_type="technical.breakout",
                    b_type="oi.spike",
                    out_type="technical.breakout_confirmed",
                    out_direction="bullish",
                    out_horizon="short",
                    suppress_inputs=False,
                )
            ]
        ),
        context_builder=DefaultContextBuilder(),
        l0_processor=HeuristicL0Processor(),
        l1_aggregator=HeuristicL1Aggregator(),
        final_gate=DeterministicFinalGate(),
        event_memory=InMemoryEventMemory(),
        layer_store=layer_store,
    )
    selected = runner.run_once()
    logger.info("事件中心最小 Runner 执行完成，selected_count=%s", len(selected))
    logger.info("selected=%s", json.dumps(selected, ensure_ascii=False))


def _build_layer_store():
    mode = str(os.getenv("EVENT_CENTER_LAYER_STORE_MODE", "memory") or "memory").strip().lower()
    if mode == "redis":
        redis_url = str(os.getenv("EVENT_CENTER_REDIS_URL", "redis://127.0.0.1:6379/0") or "").strip()
        cfg = RedisLayerStoreConfig(
            raw_stream=str(os.getenv("EVENT_CENTER_STREAM_RAW", "ec:raw") or "ec:raw").strip(),
            normalized_stream=str(os.getenv("EVENT_CENTER_STREAM_NORMALIZED", "ec:normalized") or "ec:normalized").strip(),
            evidence_stream=str(os.getenv("EVENT_CENTER_STREAM_EVIDENCE", "ec:evidence") or "ec:evidence").strip(),
            context_stream=str(os.getenv("EVENT_CENTER_STREAM_CONTEXT", "ec:context") or "ec:context").strip(),
            selected_stream=str(os.getenv("EVENT_CENTER_STREAM_SELECTED", "ec:selected") or "ec:selected").strip(),
            maxlen=int(os.getenv("EVENT_CENTER_STREAM_MAXLEN", "20000") or "20000"),
            approximate=str(os.getenv("EVENT_CENTER_STREAM_APPROX", "true") or "true").strip().lower() == "true",
        )
        logger.info("事件中心启用 Redis 分层写入，url=%s", redis_url)
        return RedisLayerStore.from_url(redis_url, cfg=cfg)
    logger.info("事件中心启用内存分层写入")
    return InMemoryLayerStore()


if __name__ == "__main__":
    main()
