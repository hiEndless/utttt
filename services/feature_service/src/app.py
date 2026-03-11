from __future__ import annotations

from fastapi import FastAPI

from services.feature_service.src.routes import create_router
from services.feature_service.src.providers.bundle import build_independent_provider_bundle
from services.feature_service.src.service import FeatureService


def create_app() -> FastAPI:
    service = FeatureService.from_bundle(build_independent_provider_bundle())

    app = FastAPI(
        title="feature_service",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    app.include_router(create_router(service))
    return app
