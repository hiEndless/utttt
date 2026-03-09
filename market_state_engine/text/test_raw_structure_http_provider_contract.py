import asyncio

import httpx
import pytest

from market_state_engine.adapters.raw_structure_http import HttpRawStructureProvider
from market_state_engine.errors import FeatureDataUnavailableFromUpstreamError


def test_http_provider_reads_new_meta_data_contract(monkeypatch):
    async def _fake_get(self, url: str):
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            request=request,
            json={
                "meta": {
                    "schema_version": "1.0",
                    "generated_at_ms": 1741411200000,
                    "degraded": False,
                    "degraded_reasons": [],
                },
                "data": {
                    "exchange": "binance",
                    "symbol": "ETHUSDT",
                    "raw_market_structure": {"symbol": "ETHUSDT", "horizons": {}},
                },
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)
    provider = HttpRawStructureProvider(base_url="http://127.0.0.1:9961", timeout_s=1.0)
    async def _run():
        out = await provider.get_raw_structure("binance", "ETHUSDT")
        assert out["symbol"] == "ETHUSDT"

    asyncio.run(_run())


def test_http_provider_maps_feature_data_unavailable(monkeypatch):
    async def _fake_get(self, url: str):
        request = httpx.Request("GET", url)
        return httpx.Response(
            503,
            request=request,
            json={
                "detail": {
                    "code": "feature_data_unavailable",
                    "degraded_reasons": ["orderbook_provider_fallback", "open_interest_provider_fallback"],
                }
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)
    provider = HttpRawStructureProvider(base_url="http://127.0.0.1:9961", timeout_s=1.0)
    async def _run():
        with pytest.raises(FeatureDataUnavailableFromUpstreamError) as exc:
            await provider.get_raw_structure("binance", "ETHUSDT")
        assert "orderbook_provider_fallback" in list(exc.value.degraded_reasons or [])

    asyncio.run(_run())


def test_http_provider_rejects_legacy_or_invalid_contract(monkeypatch):
    async def _fake_get(self, url: str):
        request = httpx.Request("GET", url)
        # 旧契约风格：顶层 raw_market_structure（已不再支持）
        return httpx.Response(
            200,
            request=request,
            json={"raw_market_structure": {"symbol": "ETHUSDT"}},
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)
    provider = HttpRawStructureProvider(base_url="http://127.0.0.1:9961", timeout_s=1.0)

    async def _run():
        with pytest.raises(TypeError, match="invalid_feature_service_contract"):
            await provider.get_raw_structure("binance", "ETHUSDT")

    asyncio.run(_run())
