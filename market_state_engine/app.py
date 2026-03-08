from __future__ import annotations

import os

from fastapi import FastAPI

from market_state_engine.adapters.raw_structure_http import HttpRawStructureProvider
from market_state_engine.routes import create_router
from market_state_engine.service import MarketStateService


def create_app() -> FastAPI:
    raw_structure_base_url = str(os.getenv("RAW_STRUCTURE_PROVIDER_URL", "http://127.0.0.1:9961") or "").strip()
    raw_structure_timeout_s = float(os.getenv("RAW_STRUCTURE_PROVIDER_TIMEOUT_S", "10") or "10")
    provider = HttpRawStructureProvider(
        base_url=raw_structure_base_url,
        timeout_s=raw_structure_timeout_s,
    )
    service = MarketStateService(raw_structure_provider=provider)
    app = FastAPI(
        title="market_state_engine",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    app.include_router(create_router(service))
    return app
