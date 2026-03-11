from services.feature_service.src.providers.bundle import ProviderBundle, build_independent_provider_bundle, build_noop_provider_bundle
from services.feature_service.src.providers.fallback_structure_providers import (
    FallbackBehaviorProvider,
    FallbackHorizonsProvider,
    FallbackOpenInterestProvider,
    FallbackOrderbookProvider,
)
from services.feature_service.src.providers.future_source_providers import (
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
from services.feature_service.src.providers.migrated_structure_providers import (
    MigratedBehaviorProvider,
    MigratedHorizonsProvider,
    MigratedOpenInterestProvider,
    MigratedOrderbookProvider,
)
from services.feature_service.src.providers.static_structure_providers import (
    StaticBehaviorProvider,
    StaticHorizonsProvider,
    StaticOpenInterestProvider,
    StaticOrderbookProvider,
)

try:
    from services.feature_service.src.providers.indicators_provider import RedisIndicatorsProvider
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
