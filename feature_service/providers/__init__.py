from feature_service.providers.bundle import ProviderBundle, build_independent_provider_bundle, build_noop_provider_bundle
from feature_service.providers.fallback_structure_providers import (
    FallbackBehaviorProvider,
    FallbackHorizonsProvider,
    FallbackOpenInterestProvider,
    FallbackOrderbookProvider,
)
from feature_service.providers.future_source_providers import (
    FallbackNewsProvider,
    FallbackOnchainProvider,
    FallbackSocialProvider,
    NoopNewsProvider,
    NoopOnchainProvider,
    NoopSocialProvider,
    StaticNewsProvider,
    StaticOnchainProvider,
    StaticSocialProvider,
    UnavailableNewsProvider,
    UnavailableOnchainProvider,
    UnavailableSocialProvider,
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

try:
    from feature_service.providers.indicators_provider import RedisIndicatorsProvider
except Exception:  # pragma: no cover - optional runtime dependency
    RedisIndicatorsProvider = None  # type: ignore[assignment]

__all__ = [
    "ProviderBundle",
    "MigratedBehaviorProvider",
    "MigratedHorizonsProvider",
    "MigratedOpenInterestProvider",
    "MigratedOrderbookProvider",
    "FallbackBehaviorProvider",
    "FallbackHorizonsProvider",
    "FallbackOpenInterestProvider",
    "FallbackOrderbookProvider",
    "StaticBehaviorProvider",
    "StaticHorizonsProvider",
    "StaticOpenInterestProvider",
    "StaticOrderbookProvider",
    "NoopNewsProvider",
    "NoopSocialProvider",
    "NoopOnchainProvider",
    "StaticNewsProvider",
    "StaticSocialProvider",
    "StaticOnchainProvider",
    "FallbackNewsProvider",
    "FallbackSocialProvider",
    "FallbackOnchainProvider",
    "UnavailableNewsProvider",
    "UnavailableSocialProvider",
    "UnavailableOnchainProvider",
    "build_noop_provider_bundle",
    "build_independent_provider_bundle",
]

if RedisIndicatorsProvider is not None:
    __all__.append("RedisIndicatorsProvider")
