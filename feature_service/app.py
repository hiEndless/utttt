from __future__ import annotations

from fastapi import FastAPI

from feature_service.adapters.behavior_compat import CompatBehaviorProvider
from feature_service.adapters.horizons_compat import CompatHorizonsProvider
from feature_service.adapters.indicators_redis import RedisIndicatorsProvider
from feature_service.adapters.open_interest_compat import CompatOpenInterestProvider
from feature_service.adapters.orderbook_compat import CompatOrderbookProvider
from feature_service.routes import create_router
from feature_service.service import FeatureService


def create_app() -> FastAPI:
    service = FeatureService(
        orderbook_provider=CompatOrderbookProvider(),
        open_interest_provider=CompatOpenInterestProvider(),
        horizons_provider=CompatHorizonsProvider(),
        behavior_provider=CompatBehaviorProvider(),
        indicators_provider=RedisIndicatorsProvider(),
    )
    app = FastAPI(
        title="feature_service",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    app.include_router(create_router(service))
    return app
