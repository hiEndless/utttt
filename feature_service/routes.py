from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from feature_service.service import FeatureService


def create_router(service: FeatureService) -> APIRouter:
    router = APIRouter(prefix="/internal/feature-service", tags=["feature-service"])

    @router.get("/healthz")
    async def healthz() -> Dict[str, Any]:
        return {"ok": True, "service": "feature_service", "ts": int(time.time() * 1000)}

    @router.get("/raw-structure/{exchange}/{symbol}")
    async def get_raw_structure(exchange: str, symbol: str) -> Dict[str, Any]:
        exchange_normalized = str(exchange or "").strip()
        symbol_normalized = str(symbol or "").strip().upper()
        if not exchange_normalized:
            raise HTTPException(status_code=400, detail="exchange_required")
        if not symbol_normalized:
            raise HTTPException(status_code=400, detail="symbol_required")

        data = await service.get_raw_structure(exchange_normalized, symbol_normalized)
        return {**data, "ts": int(time.time() * 1000)}

    @router.get("/features/{exchange}/{symbol}")
    async def get_features(exchange: str, symbol: str) -> Dict[str, Any]:
        exchange_normalized = str(exchange or "").strip()
        symbol_normalized = str(symbol or "").strip().upper()
        if not exchange_normalized:
            raise HTTPException(status_code=400, detail="exchange_required")
        if not symbol_normalized:
            raise HTTPException(status_code=400, detail="symbol_required")

        data = await service.get_features(exchange_normalized, symbol_normalized)
        return {**data, "ts": int(time.time() * 1000)}

    return router
