from __future__ import annotations

import os
import time
from typing import Any, Dict

import httpx
from fastapi import APIRouter, FastAPI, Response

from services.agent_server_new.app.bootstrap import create_trade_event_workflow_from_env
from services.agent_server_new.version import AGENT_CONTRACT_VERSION, AGENT_RUNTIME_VERSION


def _env_str(name: str, default: str) -> str:
    return str(os.getenv(name, default) or default).strip()


def _env_bool(name: str, default: str = "false") -> bool:
    return _env_str(name, default).lower() in {"1", "true", "yes", "on"}


def _record_check(*, checks: Dict[str, Any], name: str, ok: bool, detail: Dict[str, Any]) -> None:
    checks[name] = {"ok": bool(ok), **dict(detail)}


def _check_market_state_healthz(*, timeout_s: float) -> tuple[bool, Dict[str, Any]]:
    base_url = _env_str("AGENT_MARKET_STATE_BASE_URL", "http://127.0.0.1:8300").rstrip("/")
    url = f"{base_url}/internal/market-state/healthz"
    try:
        with httpx.Client(timeout=timeout_s) as client:
            response = client.get(url)
            if response.status_code // 100 != 2:
                return False, {"status_code": int(response.status_code), "url": url}
        return True, {"url": url}
    except Exception as exc:  # pragma: no cover
        return False, {"url": url, "error": str(exc)}


def _check_active_events_redis_ping() -> tuple[bool, Dict[str, Any]]:
    mode = _env_str("AGENT_ACTIVE_EVENTS_PROVIDER_MODE", "redis").lower()
    if mode != "redis":
        return True, {"skipped": True, "reason": "active_events_provider_not_redis"}
    redis_url = _env_str("AGENT_ACTIVE_EVENTS_REDIS_URL", "redis://127.0.0.1:6379/0")
    try:
        import redis  # type: ignore
    except Exception as exc:  # pragma: no cover
        return False, {"redis_url": redis_url, "error": f"redis_dependency_missing:{exc}"}
    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        ok = bool(client.ping())
        return ok, {"redis_url": redis_url}
    except Exception as exc:  # pragma: no cover
        return False, {"redis_url": redis_url, "error": str(exc)}


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

    @router.get("/version")
    async def version() -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        return {
            "service": "agent_server_new",
            "contract_version": AGENT_CONTRACT_VERSION,
            "runtime_version": AGENT_RUNTIME_VERSION,
            "runtime_profile": _env_str("AGENT_RUNTIME_PROFILE", "dev").lower(),
            "ts": now_ms,
            "ts_ms": now_ms,
        }

    @router.get("/readyz")
    async def readyz(response: Response) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        checks: Dict[str, Any] = {}
        errors: list[str] = []
        warnings: list[str] = []
        strict_upstream = _env_bool("AGENT_READY_CHECK_UPSTREAM_STRICT", "false")
        check_market_state = _env_bool("AGENT_READY_CHECK_MARKET_STATE", "true")
        check_active_events_redis = _env_bool("AGENT_READY_CHECK_ACTIVE_EVENTS_REDIS", "true")
        timeout_s = float(_env_str("AGENT_READY_CHECK_TIMEOUT_S", "1.5") or "1.5")

        try:
            wf = create_trade_event_workflow_from_env()
            _record_check(
                checks=checks,
                name="workflow_bootstrap",
                ok=True,
                detail={"workflow": wf.__class__.__name__},
            )
        except Exception as exc:  # pragma: no cover
            _record_check(
                checks=checks,
                name="workflow_bootstrap",
                ok=False,
                detail={"error": str(exc)},
            )
            errors.append("workflow_bootstrap_failed")

        if check_market_state:
            ok, detail = _check_market_state_healthz(timeout_s=timeout_s)
            _record_check(checks=checks, name="market_state_healthz", ok=ok, detail=detail)
            if not ok:
                (errors if strict_upstream else warnings).append("market_state_unreachable")

        if check_active_events_redis:
            ok, detail = _check_active_events_redis_ping()
            _record_check(checks=checks, name="active_events_redis_ping", ok=ok, detail=detail)
            if not ok:
                (errors if strict_upstream else warnings).append("active_events_redis_unreachable")

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
