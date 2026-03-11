from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from feature_service.ports.behavior_provider import BehaviorProvider
from feature_service.ports.horizons_provider import HorizonsProvider
from feature_service.ports.indicators_provider import IndicatorsProvider
from feature_service.ports.open_interest_provider import OpenInterestProvider
from feature_service.ports.orderbook_provider import OrderbookProvider
from services.feature_service.src.providers.noop import (
    NoopBehaviorProvider,
    NoopHorizonsProvider,
    NoopIndicatorsProvider,
    NoopOpenInterestProvider,
    NoopOrderbookProvider,
)
from feature_service.providers.fallback_structure_providers import (
    FallbackBehaviorProvider,
    FallbackHorizonsProvider,
    FallbackIndicatorsProvider,
    FallbackOpenInterestProvider,
    FallbackOrderbookProvider,
    UnavailableIndicatorsProvider,
)
from feature_service.providers.migrated_structure_providers import (
    MigratedBehaviorProvider,
    MigratedHorizonsProvider,
    MigratedOpenInterestProvider,
    MigratedOrderbookProvider,
)
from feature_service.providers.static_structure_providers import (
    StaticBehaviorProvider,
    StaticHorizonsProvider,
    StaticOpenInterestProvider,
    StaticOrderbookProvider,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderBundle:
    orderbook_provider: OrderbookProvider
    open_interest_provider: OpenInterestProvider
    horizons_provider: HorizonsProvider
    behavior_provider: BehaviorProvider
    indicators_provider: IndicatorsProvider


def build_noop_provider_bundle() -> ProviderBundle:
    # 纯占位模式：用于本地快速启动、契约测试或极端故障兜底。
    return ProviderBundle(
        orderbook_provider=NoopOrderbookProvider(),
        open_interest_provider=NoopOpenInterestProvider(),
        horizons_provider=NoopHorizonsProvider(),
        behavior_provider=NoopBehaviorProvider(),
        indicators_provider=NoopIndicatorsProvider(),
    )


def build_independent_provider_bundle(periods: Iterable[str] | None = None) -> ProviderBundle:
    # 独立模式：优先使用可用的 Redis 指标 provider；不可用时自动降级为空实现。
    indicators_provider: IndicatorsProvider
    try:
        from feature_service.providers.indicators_provider import RedisIndicatorsProvider

        indicators_provider = FallbackIndicatorsProvider(
            RedisIndicatorsProvider(periods=periods),
            NoopIndicatorsProvider(),
        )
    except Exception:
        logger.warning("指标Provider初始化失败，已降级为Noop实现", exc_info=True)
        indicators_provider = UnavailableIndicatorsProvider()

    static_orderbook = StaticOrderbookProvider()
    static_open_interest = StaticOpenInterestProvider()
    static_horizons = StaticHorizonsProvider()
    static_behavior = StaticBehaviorProvider()

    return ProviderBundle(
        orderbook_provider=FallbackOrderbookProvider(MigratedOrderbookProvider(), static_orderbook),
        open_interest_provider=FallbackOpenInterestProvider(MigratedOpenInterestProvider(), static_open_interest),
        horizons_provider=FallbackHorizonsProvider(MigratedHorizonsProvider(), static_horizons),
        behavior_provider=FallbackBehaviorProvider(MigratedBehaviorProvider(), static_behavior),
        indicators_provider=indicators_provider,
    )
