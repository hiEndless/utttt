from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from services.feature_service.src.contracts import (
    FeatureResponse,
    FeatureSnapshot,
    RawStructureResponse,
    RawStructureSnapshot,
    ResponseMeta,
)
from services.feature_service.src.service import FeatureDataUnavailableError, FeatureService


def create_router(service: FeatureService) -> APIRouter:
    router = APIRouter(prefix="/internal/feature-service", tags=["feature-service"])

    @router.get("/healthz")
    async def healthz() -> Dict[str, Any]:
        return {"ok": True, "service": "feature_service", "ts": int(time.time() * 1000)}

    @router.get("/raw-structure/{exchange}/{symbol}", response_model=RawStructureResponse)
    async def get_raw_structure(exchange: str, symbol: str) -> RawStructureResponse:
        exchange_normalized = str(exchange or "").strip()
        symbol_normalized = str(symbol or "").strip().upper()
        if not exchange_normalized:
            raise HTTPException(status_code=400, detail="exchange_required")
        if not symbol_normalized:
            raise HTTPException(status_code=400, detail="symbol_required")

        try:
            data = await service.get_raw_structure(exchange_normalized, symbol_normalized)
        except FeatureDataUnavailableError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "feature_data_unavailable",
                    "message": "关键结构数据不可用，请稍后重试",
                    "exchange": exc.exchange,
                    "symbol": exc.symbol,
                    "degraded_reasons": list(exc.degraded_reasons or []),
                },
            )
        ts = int(time.time() * 1000)
        return RawStructureResponse(
            meta=ResponseMeta(
                generated_at_ms=ts,
                degraded=bool(data.get("degraded")),
                degraded_reasons=list(data.get("degraded_reasons") or []),
            ),
            data=RawStructureSnapshot(
                exchange=str(data.get("exchange") or exchange_normalized),
                symbol=str(data.get("symbol") or symbol_normalized),
                raw_market_structure=dict(data.get("raw_market_structure") or {}),
            ),
        )

    @router.get("/features/{exchange}/{symbol}", response_model=FeatureResponse)
    async def get_features(exchange: str, symbol: str) -> FeatureResponse:
        exchange_normalized = str(exchange or "").strip()
        symbol_normalized = str(symbol or "").strip().upper()
        if not exchange_normalized:
            raise HTTPException(status_code=400, detail="exchange_required")
        if not symbol_normalized:
            raise HTTPException(status_code=400, detail="symbol_required")

        try:
            data = await service.get_features(exchange_normalized, symbol_normalized)
        except FeatureDataUnavailableError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "feature_data_unavailable",
                    "message": "关键结构数据不可用，请稍后重试",
                    "exchange": exc.exchange,
                    "symbol": exc.symbol,
                    "degraded_reasons": list(exc.degraded_reasons or []),
                },
            )
        payload = dict(data.get("features") or {})
        ts = int(time.time() * 1000)
        return FeatureResponse(
            meta=ResponseMeta(
                generated_at_ms=ts,
                degraded=bool(data.get("degraded")),
                degraded_reasons=list(data.get("degraded_reasons") or []),
            ),
            data=FeatureSnapshot(
                exchange=str(data.get("exchange") or exchange_normalized),
                symbol=str(data.get("symbol") or symbol_normalized),
                indicators=dict(payload.get("indicators") or {}),
                derived_metrics=dict(payload.get("derived_metrics") or {}),
                structure_snapshot=dict(payload.get("structure_snapshot") or {}),
            ),
        )

    return router
