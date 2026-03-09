from __future__ import annotations

from typing import Any, Dict

import httpx

from market_state_engine.errors import FeatureDataUnavailableFromUpstreamError
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
            if response.status_code == 503:
                # 映射上游业务错误，供 service 做短路返回而非异常中断。
                payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                detail = payload.get("detail") if isinstance(payload, dict) else {}
                if isinstance(detail, dict) and str(detail.get("code") or "") == "feature_data_unavailable":
                    raise FeatureDataUnavailableFromUpstreamError(
                        exchange=exchange,
                        symbol=symbol,
                        degraded_reasons=[str(x) for x in list(detail.get("degraded_reasons") or []) if x],
                    )
            response.raise_for_status()
            data = response.json()

        # 新契约：meta + data.raw_market_structure
        if isinstance(data, dict):
            data_block = data.get("data")
            if isinstance(data_block, dict) and isinstance(data_block.get("raw_market_structure"), dict):
                return dict(data_block.get("raw_market_structure") or {})

        raise TypeError("invalid_feature_service_contract")
