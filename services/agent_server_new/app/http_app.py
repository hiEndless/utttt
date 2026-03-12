from __future__ import annotations

import os
import time
from typing import Any, Dict

from fastapi import APIRouter, FastAPI, Response

from services.agent_server_new.app.bootstrap import create_trade_event_workflow_from_env


def _env_str(name: str, default: str) -> str:
    return str(os.getenv(name, default) or default).strip()


def _env_bool(name: str, default: str = "false") -> bool:
    return _env_str(name, default).lower() in {"1", "true", "yes", "on"}


def create_router() -> APIRouter:
    router = APIRouter(prefix="/internal/agent", tags=["agent_server_new"])

    @router.get("/healthz")
    async def healthz() -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        return {
            "ok": True,
            "service": "agent_server_new",
            "runtime_profile": _env_str("AGENT_RUNTIME_PROFILE", "dev"),
            "ts": now_ms,
            "ts_ms": now_ms,
        }

    @router.get("/readyz")
    async def readyz(response: Response) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        checks: Dict[str, Any] = {}
        errors: list[str] = []
        warnings: list[str] = []

        try:
            wf = create_trade_event_workflow_from_env()
            checks["workflow_bootstrap"] = {
                "ok": True,
                "workflow": wf.__class__.__name__,
            }
        except Exception as exc:  # pragma: no cover
            checks["workflow_bootstrap"] = {"ok": False, "error": str(exc)}
            errors.append("workflow_bootstrap_failed")

        runtime_profile = _env_str("AGENT_RUNTIME_PROFILE", "dev").lower()
        execution_enabled = _env_bool("AGENT_EXECUTION_ENABLED", "false")
        if runtime_profile in {"prod", "production"} and not execution_enabled:
            warnings.append("execution_decider_disabled_in_production")

        ok = len(errors) == 0
        if not ok:
            response.status_code = 503
        return {
            "ok": ok,
            "service": "agent_server_new",
            "runtime_profile": runtime_profile,
            "checks": checks,
            "warnings": warnings,
            "errors": errors,
            "ts": now_ms,
            "ts_ms": now_ms,
        }

    return router


def create_app() -> FastAPI:
    app = FastAPI(
        title="agent_server_new",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    app.include_router(create_router())
    return app


__all__ = ["create_app", "create_router"]

