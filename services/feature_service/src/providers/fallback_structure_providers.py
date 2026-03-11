from __future__ import annotations

import logging
from typing import Any, Dict

from services.feature_service.src.ports.behavior_provider import BehaviorProvider
from services.feature_service.src.ports.horizons_provider import HorizonsProvider
from services.feature_service.src.ports.indicators_provider import IndicatorsProvider
from services.feature_service.src.ports.open_interest_provider import OpenInterestProvider
from services.feature_service.src.ports.orderbook_provider import OrderbookProvider
from services.feature_service.src.providers.degradation_state import mark_degraded

logger = logging.getLogger(__name__)


class FallbackOrderbookProvider(OrderbookProvider):
    # 优先走迁移后的主 provider，失败后自动降级到 fallback，保证服务可用性。
    def __init__(self, primary: OrderbookProvider, fallback: OrderbookProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def get_orderbook(self, exchange: str, symbol: str) -> Dict[str, Any]:
        try:
            return dict(await self._primary.get_orderbook(exchange, symbol) or {})
        except Exception:
            mark_degraded("orderbook_provider_fallback")
            logger.warning(
                "订单簿主Provider失败，已降级到备用Provider exchange=%s symbol=%s",
                exchange,
                symbol,
                exc_info=True,
            )
            return dict(await self._fallback.get_orderbook(exchange, symbol) or {})


class FallbackOpenInterestProvider(OpenInterestProvider):
    # OI 结构读取失败时走降级路径，避免上游波动导致接口直接失败。
    def __init__(self, primary: OpenInterestProvider, fallback: OpenInterestProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def get_open_interest(self, exchange: str, symbol: str) -> Dict[str, Any]:
        try:
            return dict(await self._primary.get_open_interest(exchange, symbol) or {})
        except Exception:
            mark_degraded("open_interest_provider_fallback")
            logger.warning(
                "持仓量主Provider失败，已降级到备用Provider exchange=%s symbol=%s",
                exchange,
                symbol,
                exc_info=True,
            )
            return dict(await self._fallback.get_open_interest(exchange, symbol) or {})


class FallbackHorizonsProvider(HorizonsProvider):
    # Horizons 聚合失败时保底返回静态结构，优先保证服务链路可达。
    def __init__(self, primary: HorizonsProvider, fallback: HorizonsProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def get_horizons(self, exchange: str, symbol: str) -> Dict[str, Any]:
        try:
            return dict(await self._primary.get_horizons(exchange, symbol) or {})
        except Exception:
            mark_degraded("horizons_provider_fallback")
            logger.warning(
                "多周期主Provider失败，已降级到备用Provider exchange=%s symbol=%s",
                exchange,
                symbol,
                exc_info=True,
            )
            return dict(await self._fallback.get_horizons(exchange, symbol) or {})


class FallbackBehaviorProvider(BehaviorProvider):
    # 行为结构失败时也执行同样降级策略，保证 pre_decision_structure 能构建。
    def __init__(self, primary: BehaviorProvider, fallback: BehaviorProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def get_behavior(self, exchange: str, symbol: str) -> Dict[str, Any]:
        try:
            return dict(await self._primary.get_behavior(exchange, symbol) or {})
        except Exception:
            mark_degraded("behavior_provider_fallback")
            logger.warning(
                "行为结构主Provider失败，已降级到备用Provider exchange=%s symbol=%s",
                exchange,
                symbol,
                exc_info=True,
            )
            return dict(await self._fallback.get_behavior(exchange, symbol) or {})


class FallbackIndicatorsProvider(IndicatorsProvider):
    # 指标读取异常时降级为空指标，保证 features 接口可用。
    def __init__(self, primary: IndicatorsProvider, fallback: IndicatorsProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def get_indicators(self, exchange: str, symbol: str) -> Dict[str, Any]:
        try:
            return dict(await self._primary.get_indicators(exchange, symbol) or {})
        except Exception:
            mark_degraded("indicators_provider_fallback")
            logger.warning(
                "指标主Provider失败，已降级到备用Provider exchange=%s symbol=%s",
                exchange,
                symbol,
                exc_info=True,
            )
            return dict(await self._fallback.get_indicators(exchange, symbol) or {})


class UnavailableIndicatorsProvider(IndicatorsProvider):
    # 指标 provider 在初始化阶段不可用时使用该实现，显式标记降级。
    async def get_indicators(self, exchange: str, symbol: str) -> Dict[str, Any]:
        mark_degraded("indicators_provider_unavailable")
        return {}
