import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.feature_service.src.providers.degradation_state import (
    reset_degradation_state,
    snapshot_degradation_reasons,
)
from services.feature_service.src.providers.future_source_providers import (
    FallbackNewsProvider,
    StaticNewsProvider,
    UnavailableOnchainProvider,
)


class _BrokenNewsProvider:
    async def get_news_features(self, exchange: str, symbol: str):
        raise RuntimeError("news_primary_failed")


class _FixedNewsProvider:
    async def get_news_features(self, exchange: str, symbol: str):
        return {"headline_score": 0.7, "source": "stub"}


def test_fallback_news_provider_uses_fallback_and_records_degraded_reason():
    async def _run():
        reset_degradation_state()
        provider = FallbackNewsProvider(_BrokenNewsProvider(), _FixedNewsProvider())
        out = await provider.get_news_features("binance", "BTCUSDT")
        reasons = snapshot_degradation_reasons()

        assert out.get("source_type") == "news"
        assert out.get("provider_state") == "fallback"
        assert out.get("available") is True
        assert out.get("features", {}).get("headline_score") == 0.7
        assert "news_provider_fallback" in reasons

    asyncio.run(_run())


def test_static_news_provider_returns_deepcopy_payload():
    async def _run():
        payload = {"items": [{"title": "a"}]}
        provider = StaticNewsProvider(payload)
        out = await provider.get_news_features("binance", "ETHUSDT")
        out["features"]["items"][0]["title"] = "mutated"

        out2 = await provider.get_news_features("binance", "ETHUSDT")
        assert out2.get("provider_state") == "static"
        assert out2["features"]["items"][0]["title"] == "a"

    asyncio.run(_run())


def test_unavailable_onchain_provider_marks_degraded():
    async def _run():
        reset_degradation_state()
        provider = UnavailableOnchainProvider()
        out = await provider.get_onchain_features("binance", "SOLUSDT")
        reasons = snapshot_degradation_reasons()

        assert out.get("source_type") == "onchain"
        assert out.get("provider_state") == "unavailable"
        assert out.get("available") is False
        assert out.get("features") == {}
        assert "onchain_provider_unavailable" in reasons

    asyncio.run(_run())
