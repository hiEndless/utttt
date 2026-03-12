import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.market_state_engine.src.errors import FeatureDataUnavailableFromUpstreamError
from services.market_state_engine.src.service import MarketStateService


MSL_ALLOWED_KEYS = {
    "version",
    "timestamp",
    "symbol",
    "market_regime",
    "liquidity_state",
    "positioning_state",
    "volatility_state",
    "risk_state",
    "market_structure_state",
    "key_levels",
    "anomalies",
    "summary",
}


class _OkRawProvider:
    async def get_raw_structure(self, exchange: str, symbol: str):
        return {
            "symbol": symbol,
            "horizons": {},
            "orderbook": {},
            "open_interest": {},
            "behavioral": {},
            "pre_decision_structure": {},
        }


class _UnavailableRawProvider:
    async def get_raw_structure(self, exchange: str, symbol: str):
        raise FeatureDataUnavailableFromUpstreamError(
            exchange=exchange,
            symbol=symbol,
            degraded_reasons=["feature_data_unavailable"],
        )


def test_msl_whitelist_on_ok_branch():
    async def _run():
        service = MarketStateService(raw_structure_provider=_OkRawProvider())
        out = await service.get_market_state("binance", "ETHUSDT")
        msl = dict(out.get("msl") or {})
        assert set(msl.keys()) == MSL_ALLOWED_KEYS

    asyncio.run(_run())


def test_msl_whitelist_on_data_unavailable_branch():
    async def _run():
        service = MarketStateService(raw_structure_provider=_UnavailableRawProvider())
        out = await service.get_market_state("binance", "ETHUSDT")
        msl = dict(out.get("msl") or {})
        assert set(msl.keys()) == MSL_ALLOWED_KEYS

    asyncio.run(_run())
