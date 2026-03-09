from __future__ import annotations

from fastapi import FastAPI

from execution_service.adapters.stub_risk_policy_provider import StubRiskPolicyProvider
from execution_service.adapters.stub_state_providers import (
    StubAccountStateProvider,
    StubPositionStateProvider,
)
from execution_service.app.service import ExecutionService
from execution_service.routes import create_router


def create_app() -> FastAPI:
    service = ExecutionService(
        position_provider=StubPositionStateProvider(),
        account_provider=StubAccountStateProvider(),
        risk_policy_provider=StubRiskPolicyProvider(),
    )
    app = FastAPI(
        title="execution_service",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    app.include_router(create_router(service))
    return app
