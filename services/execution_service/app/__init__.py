"""execution_service app layer."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI

from services.execution_service.adapters.redis_state_providers import (
    RedisAccountStateProvider,
    RedisExecutionStateConfig,
    RedisPositionStateProvider,
    RedisRiskPolicyProvider,
    create_redis_client_from_env,
)
from services.execution_service.adapters.confidence_metrics_store import (
    InMemoryConfidenceMetricsStore,
    RedisConfidenceMetricsStore,
)
from services.execution_service.adapters.mock_execution_sink import MockExecutionSink
from services.execution_service.adapters.exchange_execution_sink import ExchangeExecutionSink
from services.execution_service.adapters.idempotency_store import InMemoryIdempotencyStore, RedisIdempotencyStore
from services.execution_service.adapters.execution_state_store import InMemoryExecutionStateStore, RedisExecutionStateStore
from services.execution_service.adapters.stub_risk_policy_provider import StubRiskPolicyProvider
from services.execution_service.adapters.stub_state_providers import (
    StubAccountStateProvider,
    StubPositionStateProvider,
)
from services.execution_service.routes import create_router
from .service import ExecutionService

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    state_provider_mode = str(os.getenv("EXECUTION_STATE_PROVIDER_MODE", "stub") or "stub").strip().lower()
    redis_client = None
    cfg = None

    if state_provider_mode == "redis":
        cfg = RedisExecutionStateConfig.from_env()
        redis_client = create_redis_client_from_env(cfg.redis_url)
        position_provider = RedisPositionStateProvider(
            redis_client=redis_client,
            key_template=cfg.position_key_template,
        )
        account_provider = RedisAccountStateProvider(
            redis_client=redis_client,
            key_template=cfg.account_key_template,
        )
        risk_policy_provider = RedisRiskPolicyProvider(
            redis_client=redis_client,
            key_template=cfg.risk_policy_key_template,
        )
        logger.info("execution_service 使用 Redis 状态提供器，redis_url=%s", cfg.redis_url)
    else:
        position_provider = StubPositionStateProvider()
        account_provider = StubAccountStateProvider()
        risk_policy_provider = StubRiskPolicyProvider()
        logger.info("execution_service 使用 Stub 状态提供器")

    submit_enabled = str(os.getenv("EXECUTION_SUBMIT_ENABLED", "false") or "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    sink_mode = str(os.getenv("EXECUTION_SINK_MODE", "mock") or "mock").strip().lower()
    execution_sink = None
    if submit_enabled:
        if sink_mode == "mock":
            execution_sink = MockExecutionSink(
                venue=str(os.getenv("EXECUTION_SINK_MOCK_VENUE", "mock_exchange") or "mock_exchange").strip()
            )
            logger.info("execution_service 启用执行下沉，mode=mock")
        elif sink_mode == "exchange":
            execution_sink = ExchangeExecutionSink(
                venue=str(os.getenv("EXECUTION_SINK_EXCHANGE_VENUE", "binance") or "binance").strip(),
                dry_run=str(
                    os.getenv("EXECUTION_SINK_EXCHANGE_DRY_RUN", "true") or "true"
                ).strip().lower() in {"1", "true", "yes", "on"},
                api_base_url=str(
                    os.getenv("EXECUTION_SINK_EXCHANGE_API_BASE_URL", "https://api.binance.com")
                    or "https://api.binance.com"
                ).strip(),
                api_key=str(os.getenv("EXECUTION_SINK_EXCHANGE_API_KEY", "") or "").strip(),
                api_secret=str(os.getenv("EXECUTION_SINK_EXCHANGE_API_SECRET", "") or "").strip(),
                recv_window_ms=int(str(os.getenv("EXECUTION_SINK_EXCHANGE_RECV_WINDOW_MS", "5000") or "5000")),
                default_order_qty=float(
                    str(os.getenv("EXECUTION_SINK_EXCHANGE_DEFAULT_ORDER_QTY", "0.001") or "0.001")
                ),
                timeout_s=float(str(os.getenv("EXECUTION_SINK_EXCHANGE_TIMEOUT_S", "5") or "5")),
            )
            logger.info(
                "execution_service 启用执行下沉，mode=exchange_skeleton dry_run=%s",
                getattr(execution_sink, "dry_run", True),
            )
        else:
            logger.warning("execution_service submit 已启用，但未识别 sink_mode=%s，回退禁用 submit", sink_mode)
            submit_enabled = False

    idempotency_enabled = str(os.getenv("EXECUTION_IDEMPOTENCY_ENABLED", "true") or "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    idempotency_mode = str(os.getenv("EXECUTION_IDEMPOTENCY_MODE", "memory") or "memory").strip().lower()
    idempotency_store = None
    if idempotency_enabled:
        if idempotency_mode == "redis":
            redis_url = str(
                os.getenv("EXECUTION_IDEMPOTENCY_REDIS_URL", (cfg.redis_url if cfg is not None else "redis://127.0.0.1:6379/0"))
                or (cfg.redis_url if cfg is not None else "redis://127.0.0.1:6379/0")
            ).strip()
            idem_ttl_s = int(str(os.getenv("EXECUTION_IDEMPOTENCY_TTL_S", "3600") or "3600"))
            key_template = str(
                os.getenv("EXECUTION_IDEMPOTENCY_KEY_TEMPLATE", "execution:idempotency:{decision_id}")
                or "execution:idempotency:{decision_id}"
            ).strip()
            idem_client = redis_client if (redis_client is not None and cfg is not None and redis_url == cfg.redis_url) else create_redis_client_from_env(redis_url)
            idempotency_store = RedisIdempotencyStore(
                redis_client=idem_client,
                key_template=key_template,
                ttl_s=idem_ttl_s,
            )
            logger.info("execution_service 启用幂等缓存，mode=redis ttl=%s", idem_ttl_s)
        else:
            idempotency_store = InMemoryIdempotencyStore()
            logger.info("execution_service 启用幂等缓存，mode=memory")

    execution_state_enabled = str(os.getenv("EXECUTION_STATE_MACHINE_ENABLED", "true") or "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    execution_state_mode = str(os.getenv("EXECUTION_STATE_MACHINE_MODE", "memory") or "memory").strip().lower()
    execution_state_store = None
    if execution_state_enabled:
        if execution_state_mode == "redis":
            redis_url = str(
                os.getenv(
                    "EXECUTION_STATE_MACHINE_REDIS_URL",
                    (cfg.redis_url if cfg is not None else "redis://127.0.0.1:6379/0"),
                )
                or (cfg.redis_url if cfg is not None else "redis://127.0.0.1:6379/0")
            ).strip()
            key_template = str(
                os.getenv("EXECUTION_STATE_MACHINE_KEY_TEMPLATE", "execution:state:{decision_id}")
                or "execution:state:{decision_id}"
            ).strip()
            ttl_s = int(str(os.getenv("EXECUTION_STATE_MACHINE_TTL_S", "86400") or "86400"))
            state_client = redis_client if (redis_client is not None and cfg is not None and redis_url == cfg.redis_url) else create_redis_client_from_env(redis_url)
            execution_state_store = RedisExecutionStateStore(
                redis_client=state_client,
                key_template=key_template,
                ttl_s=ttl_s,
            )
            logger.info("execution_service 启用执行状态机存储，mode=redis ttl=%s", ttl_s)
        else:
            execution_state_store = InMemoryExecutionStateStore()
            logger.info("execution_service 启用执行状态机存储，mode=memory")

    confidence_metrics_mode = str(os.getenv("EXECUTION_CONFIDENCE_METRICS_MODE", "memory") or "memory").strip().lower()
    confidence_metrics_store = None
    if confidence_metrics_mode == "redis":
        metrics_redis_url = str(
            os.getenv(
                "EXECUTION_CONFIDENCE_METRICS_REDIS_URL",
                (cfg.redis_url if cfg is not None else "redis://127.0.0.1:6379/0"),
            )
            or (cfg.redis_url if cfg is not None else "redis://127.0.0.1:6379/0")
        ).strip()
        metrics_key = str(
            os.getenv("EXECUTION_CONFIDENCE_METRICS_KEY", "execution:metrics:confidence_migration")
            or "execution:metrics:confidence_migration"
        ).strip()
        metrics_client = (
            redis_client
            if (redis_client is not None and cfg is not None and metrics_redis_url == cfg.redis_url)
            else create_redis_client_from_env(metrics_redis_url)
        )
        confidence_metrics_store = RedisConfidenceMetricsStore(redis_client=metrics_client, key=metrics_key)
        logger.info("execution_service 启用 confidence 迁移指标存储，mode=redis key=%s", metrics_key)
    else:
        confidence_metrics_store = InMemoryConfidenceMetricsStore()
        logger.info("execution_service 启用 confidence 迁移指标存储，mode=memory")

    service = ExecutionService(
        position_provider=position_provider,
        account_provider=account_provider,
        risk_policy_provider=risk_policy_provider,
        execution_sink=execution_sink,
        submit_enabled=submit_enabled,
        submit_max_retries=int(str(os.getenv("EXECUTION_SUBMIT_MAX_RETRIES", "0") or "0")),
        submit_backoff_base_s=float(str(os.getenv("EXECUTION_SUBMIT_BACKOFF_BASE_S", "0.2") or "0.2")),
        reconcile_max_retries=int(str(os.getenv("EXECUTION_RECONCILE_MAX_RETRIES", "0") or "0")),
        reconcile_backoff_base_s=float(str(os.getenv("EXECUTION_RECONCILE_BACKOFF_BASE_S", "0.2") or "0.2")),
        idempotency_store=idempotency_store,
        idempotency_lock_ttl_s=int(str(os.getenv("EXECUTION_IDEMPOTENCY_LOCK_TTL_S", "30") or "30")),
        execution_state_store=execution_state_store,
        confidence_metrics_store=confidence_metrics_store,
    )
    allow_debug_metrics_reset = str(os.getenv("EXECUTION_DEBUG_ALLOW_METRICS_RESET", "false") or "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    app = FastAPI(
        title="execution_service",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    app.include_router(create_router(service, allow_debug_metrics_reset=allow_debug_metrics_reset))
    return app


__all__ = [
    "ExecutionService",
    "create_app",
    "create_redis_client_from_env",
]
