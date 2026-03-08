from __future__ import annotations

from typing import Any, Dict

import httpx

from market_state_engine.ports.raw_structure_provider import RawStructureProvider


class HttpRawStructureProvider(RawStructureProvider):
    """通过 HTTP 读取独立 raw structure 服务。
    """

    def __init__(self, base_url: str, *, timeout_s: float = 10.0) -> None:
        self._base_url = str(base_url or "").rstrip("/")
        self._timeout_s = float(timeout_s)

    async def get_raw_structure(self, exchange: str, symbol: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            url = f"{self._base_url}/internal/feature-service/raw-structure/{exchange}/{symbol}"
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        if isinstance(data, dict) and isinstance(data.get("raw_market_structure"), dict):
            return dict(data.get("raw_market_structure") or {})
        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            return dict(data.get("data") or {})
        return dict(data or {})
