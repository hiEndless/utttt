from __future__ import annotations

import json
import logging
import os
import time
from typing import Callable

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
    run_loop = _read_bool_env("EVENT_CENTER_RUN_LOOP", default=False)
    interval_ms = _read_int_env("EVENT_CENTER_RUN_INTERVAL_MS", default=1000)
    max_ticks = _read_int_env("EVENT_CENTER_RUN_MAX_TICKS", default=0)
    stop_on_error = _read_bool_env("EVENT_CENTER_STOP_ON_ERROR", default=False)
    health_key = str(os.getenv("EVENT_CENTER_HEALTH_KEY", "ec:runner:health") or "ec:runner:health").strip()
    if run_loop:
        logger.info(
            "事件中心进入循环运行模式 interval_ms=%s max_ticks=%s stop_on_error=%s health_key=%s",
            interval_ms,
            max_ticks,
            stop_on_error,
            health_key,
        )
        _run_loop(
            runner,
            layer_store=layer_store,
            interval_ms=interval_ms,
            max_ticks=max_ticks,
            stop_on_error=stop_on_error,
            health_key=health_key,
        )
        return
    _run_once_and_log(
        runner,
        layer_store=layer_store,
        stop_on_error=stop_on_error,
        health_key=health_key,
    )


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


def _run_once_and_log(
    runner: EventPipelineRunner,
    *,
    layer_store: object | None = None,
    stop_on_error: bool = False,
    health_key: str = "ec:runner:health",
) -> None:
    selected = runner.run_once(stop_on_error=stop_on_error)
    health = runner.health_snapshot()
    _publish_runner_health(layer_store, payload=dict(health.__dict__), key=health_key)
    logger.info("事件中心最小 Runner 执行完成，selected_count=%s", len(selected))
    logger.info("runner_health=%s", json.dumps(health.__dict__, ensure_ascii=False))
    logger.info("selected=%s", json.dumps(selected, ensure_ascii=False))


def _run_loop(
    runner: EventPipelineRunner,
    *,
    layer_store: object | None = None,
    interval_ms: int,
    max_ticks: int = 0,
    stop_on_error: bool = False,
    health_key: str = "ec:runner:health",
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    tick = 0
    safe_interval = max(1, int(interval_ms))
    while True:
        tick += 1
        _run_once_and_log(
            runner,
            layer_store=layer_store,
            stop_on_error=stop_on_error,
            health_key=health_key,
        )
        if max_ticks > 0 and tick >= max_ticks:
            logger.info("事件中心循环运行达到上限，准备退出 tick=%s", tick)
            return
        sleep_fn(safe_interval / 1000.0)


def _publish_runner_health(layer_store: object | None, *, payload: dict, key: str) -> None:
    if layer_store is None:
        return
    writer = getattr(layer_store, "write_runner_health", None)
    if not callable(writer):
        return
    try:
        out = dict(payload)
        out["updated_ms"] = int(time.time() * 1000)
        writer(out, key=key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("写入 runner health 失败 key=%s err=%s", key, exc)


def _read_bool_env(name: str, *, default: bool) -> bool:
    value = str(os.getenv(name, "") or "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _read_int_env(name: str, *, default: int) -> int:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except Exception:  # noqa: BLE001
        logger.warning("环境变量解析失败，使用默认值 key=%s value=%s default=%s", name, raw, default)
        return default


if __name__ == "__main__":
    main()
