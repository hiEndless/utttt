from __future__ import annotations

from fastapi import FastAPI

from feature_service.providers.bundle import build_independent_provider_bundle
from feature_service.service import FeatureService
from services.feature_service.src.routes import create_router


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
