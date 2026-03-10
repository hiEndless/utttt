from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from execution_service.app.service import ExecutionService
from execution_service.version import (
    CONTRACT_VERSION,
    IDEMPOTENCY_VERSION,
    RULESET_VERSION,
    SCHEMA_MAPPING_VERSION,
    STATE_MACHINE_VERSION,
)


def create_router(service: ExecutionService) -> APIRouter:
    router = APIRouter(prefix="/internal/execution", tags=["execution"])

    @router.get("/healthz")
    async def healthz() -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        return {"ok": True, "service": "execution_service", "ts": now_ms, "ts_ms": now_ms}

    @router.get("/version")
    async def version() -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        return {
            "service": "execution_service",
            "contract_version": CONTRACT_VERSION,
            "ruleset_version": RULESET_VERSION,
            "state_machine_version": STATE_MACHINE_VERSION,
            "idempotency_version": IDEMPOTENCY_VERSION,
            "schema_mapping_version": SCHEMA_MAPPING_VERSION,
            "ts": now_ms,
            "ts_ms": now_ms,
        }

    @router.post("/decide")
    async def decide(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = await service.decide(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=502, detail=f"execution_decide_failed:{exc}") from exc
        return result.to_dict()

    @router.post("/reconcile")
    async def reconcile(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return await service.reconcile_order(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            msg = str(exc)
            if msg == "execution_sink_not_configured":
                raise HTTPException(status_code=503, detail=msg) from exc
            if msg == "execution_sink_reconcile_not_supported":
                raise HTTPException(status_code=501, detail=msg) from exc
            if msg.startswith("execution_reconcile_failed:"):
                raise HTTPException(status_code=502, detail=msg) from exc
            raise HTTPException(status_code=502, detail=f"execution_reconcile_failed:{exc}") from exc
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=502, detail=f"execution_reconcile_failed:{exc}") from exc

    @router.get("/debug/state/{exchange}/{symbol}")
    async def debug_state(
        exchange: str,
        symbol: str,
        account_id: str = "main",
        redact: bool = False,
        decision_id: str | None = None,
    ) -> Dict[str, Any]:
        exchange_normalized = str(exchange or "").strip()
        symbol_normalized = str(symbol or "").strip().upper()
        if not exchange_normalized:
            raise HTTPException(status_code=400, detail="exchange_required")
        if not symbol_normalized:
            raise HTTPException(status_code=400, detail="symbol_required")
        try:
            return await service.get_debug_state(
                exchange=exchange_normalized,
                symbol=symbol_normalized,
                account_id=(str(account_id).strip() or "main"),
                redact=bool(redact),
                decision_id=(str(decision_id).strip() if decision_id else None),
            )
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=502, detail=f"execution_debug_state_failed:{exc}") from exc

    @router.get("/debug/confidence-metrics")
    async def confidence_metrics() -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        return {
            "service": "execution_service",
            "confidence_migration_metrics": service.get_confidence_migration_metrics(),
            "ts": now_ms,
            "ts_ms": now_ms,
        }

    return router
