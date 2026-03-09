import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from feature_service.providers.market_structure_migrated.behavioral import behavior_output
from feature_service.providers.fallback_structure_providers import FallbackOrderbookProvider
from feature_service.providers.noop import (
    NoopBehaviorProvider,
    NoopHorizonsProvider,
    NoopIndicatorsProvider,
    NoopOpenInterestProvider,
    NoopOrderbookProvider,
)
from feature_service.providers.bundle import ProviderBundle
from feature_service.service import FeatureDataUnavailableError, FeatureService


class _BrokenOrderbookProvider:
    async def get_orderbook(self, exchange: str, symbol: str):
        raise RuntimeError("primary_failed")


class _FixedOrderbookProvider:
    async def get_orderbook(self, exchange: str, symbol: str):
        return {"orderbook_snapshot": {"spread": 1.0}}


class _StubAggTradesClient:
    async def xrevrange(self, key: str, max: str, min: str, count: int):
        return [("1-0", {"ts": "1000", "p": "1"})]


def test_fallback_orderbook_provider_uses_fallback_when_primary_failed():
    async def _run():
        provider = FallbackOrderbookProvider(_BrokenOrderbookProvider(), _FixedOrderbookProvider())
        out = await provider.get_orderbook("binance", "BTCUSDT")
        assert out.get("orderbook_snapshot", {}).get("spread") == 1.0

    asyncio.run(_run())


def test_feature_service_contract_with_noop_bundle():
    async def _run():
        service = FeatureService.from_bundle(
            ProviderBundle(
                orderbook_provider=NoopOrderbookProvider(),
                open_interest_provider=NoopOpenInterestProvider(),
                horizons_provider=NoopHorizonsProvider(),
                behavior_provider=NoopBehaviorProvider(),
                indicators_provider=NoopIndicatorsProvider(),
            )
        )

        try:
            await service.get_raw_structure("binance", "BTCUSDT")
            assert False, "预期应抛出 FeatureDataUnavailableError"
        except FeatureDataUnavailableError:
            pass

    asyncio.run(_run())


def test_behavior_output_helper_uses_dynamic_redis_client_when_client_not_provided():
    async def _run():
        original_get_redis_client = behavior_output.get_redis_client
        behavior_output.get_redis_client = lambda: _StubAggTradesClient()
        try:
            out = await behavior_output.read_recent_aggtrades(
                "binance",
                "ETHUSDT",
                max_window_ms=500,
                now_ms=1000,
                client=None,
            )
            assert isinstance(out, list)
            assert len(out) == 1
            assert out[0].get("p") == "1"
        finally:
            behavior_output.get_redis_client = original_get_redis_client

    asyncio.run(_run())


def test_feature_service_records_degraded_reason_when_fallback_happens():
    async def _run():
        service = FeatureService.from_bundle(
            ProviderBundle(
                orderbook_provider=FallbackOrderbookProvider(_BrokenOrderbookProvider(), _FixedOrderbookProvider()),
                open_interest_provider=NoopOpenInterestProvider(),
                horizons_provider=NoopHorizonsProvider(),
                behavior_provider=NoopBehaviorProvider(),
                indicators_provider=NoopIndicatorsProvider(),
            )
        )
        raw = await service.get_raw_structure("binance", "BTCUSDT")
        assert raw.get("degraded") is True
        assert "orderbook_provider_fallback" in list(raw.get("degraded_reasons") or [])

    asyncio.run(_run())


def test_feature_service_contract_with_partial_non_empty_structure():
    class _OrderbookProvider:
        async def get_orderbook(self, exchange: str, symbol: str):
            return {"orderbook_snapshot": {"spread": 1.0}, "orderbook_structure_short": {"liquidity_stability": "stable"}}

    async def _run():
        service = FeatureService.from_bundle(
            ProviderBundle(
                orderbook_provider=_OrderbookProvider(),
                open_interest_provider=NoopOpenInterestProvider(),
                horizons_provider=NoopHorizonsProvider(),
                behavior_provider=NoopBehaviorProvider(),
                indicators_provider=NoopIndicatorsProvider(),
            )
        )
        raw = await service.get_raw_structure("binance", "BTCUSDT")
        assert raw["exchange"] == "binance"
        assert raw["symbol"] == "BTCUSDT"
        assert isinstance(raw.get("raw_market_structure"), dict)

        features = await service.get_features("binance", "BTCUSDT")
        assert features["exchange"] == "binance"
        assert features["symbol"] == "BTCUSDT"
        root = features.get("features", {})
        assert isinstance(root.get("indicators"), dict)
        assert isinstance(root.get("derived_metrics"), dict)
        assert isinstance(root.get("structure_snapshot"), dict)

    asyncio.run(_run())
