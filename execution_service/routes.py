from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from execution_service.app.service import ExecutionService


def create_router(service: ExecutionService) -> APIRouter:
    router = APIRouter(prefix="/internal/execution", tags=["execution"])

    @router.get("/healthz")
    async def healthz() -> Dict[str, Any]:
        return {"ok": True, "service": "execution_service", "ts": int(time.time() * 1000)}

    @router.post("/decide")
    async def decide(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = await service.decide(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=502, detail=f"execution_decide_failed:{exc}") from exc
        return result.to_dict()

    return router
