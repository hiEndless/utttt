from __future__ import annotations

import os

from fastapi import FastAPI

from market_state_engine.adapters.raw_structure_http import HttpRawStructureProvider
from market_state_engine.adapters.selected_events_redis import (
    RedisSelectedEventProvider,
    RedisSelectedEventProviderConfig,
)
from market_state_engine.routes import create_router
from market_state_engine.service import MarketStateService


def create_app() -> FastAPI:
    raw_structure_base_url = str(os.getenv("RAW_STRUCTURE_PROVIDER_URL", "http://127.0.0.1:9961") or "").strip()
    raw_structure_timeout_s = float(os.getenv("RAW_STRUCTURE_PROVIDER_TIMEOUT_S", "10") or "10")
    provider = HttpRawStructureProvider(
        base_url=raw_structure_base_url,
        timeout_s=raw_structure_timeout_s,
    )
    selected_event_provider = None
    selected_event_mode = str(os.getenv("MSE_SELECTED_EVENT_PROVIDER_MODE", "none") or "none").strip().lower()
    if selected_event_mode == "redis":
        selected_event_redis_url = str(os.getenv("MSE_SELECTED_EVENT_REDIS_URL", "redis://127.0.0.1:6379/0") or "").strip()
        selected_event_stream = str(os.getenv("MSE_SELECTED_EVENT_STREAM", "ec:selected") or "").strip() or "ec:selected"
        selected_event_limit_default = int(os.getenv("MSE_SELECTED_EVENT_LIMIT_DEFAULT", "20") or "20")
        selected_event_scan_factor = int(os.getenv("MSE_SELECTED_EVENT_SCAN_FACTOR", "5") or "5")
        selected_event_provider = RedisSelectedEventProvider.from_url(
            selected_event_redis_url,
            cfg=RedisSelectedEventProviderConfig(
                stream=selected_event_stream,
                limit_default=selected_event_limit_default,
                scan_factor=selected_event_scan_factor,
            ),
        )

    service = MarketStateService(
        raw_structure_provider=provider,
        selected_event_provider=selected_event_provider,
    )
    app = FastAPI(
        title="market_state_engine",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    app.include_router(create_router(service))
    return app
