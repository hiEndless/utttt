from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from services.market_state_engine.src.service import MarketStateService
from services.market_state_engine.src.version import MARKET_STATE_CONTRACT_VERSION, MSL_SCHEMA_VERSION


def create_router(service: MarketStateService) -> APIRouter:
    router = APIRouter(prefix="/internal/market-state", tags=["market-state"])

    @router.get("/healthz")
    async def healthz() -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        return {"ok": True, "service": "market_state_engine", "ts": now_ms, "ts_ms": now_ms}

    @router.get("/version")
    async def version() -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        return {
            "service": "market_state_engine",
            "contract_version": MARKET_STATE_CONTRACT_VERSION,
            "msl_schema_version": int(MSL_SCHEMA_VERSION),
            "ts": now_ms,
            "ts_ms": now_ms,
        }

    @router.get("/{exchange}/{symbol}")
    async def get_market_state(exchange: str, symbol: str) -> Dict[str, Any]:
        exchange_normalized = str(exchange or "").strip()
        symbol_normalized = str(symbol or "").strip().upper()
        if not exchange_normalized:
            raise HTTPException(status_code=400, detail="exchange_required")
        if not symbol_normalized:
            raise HTTPException(status_code=400, detail="symbol_required")

        try:
            data = await service.get_market_state(exchange=exchange_normalized, symbol=symbol_normalized)
        except TypeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        now_ms = int(time.time() * 1000)
        return {
            **data,
            "ts": now_ms,
            "ts_ms": now_ms,
        }

    return router
