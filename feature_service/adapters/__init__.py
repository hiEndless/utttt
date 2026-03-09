"""Feature service adapters."""

from .behavior_compat import CompatBehaviorProvider
from .horizons_compat import CompatHorizonsProvider
from .indicators_redis import RedisIndicatorsProvider
from .open_interest_compat import CompatOpenInterestProvider
from .orderbook_compat import CompatOrderbookProvider

__all__ = [
    "CompatBehaviorProvider",
    "CompatHorizonsProvider",
    "CompatOpenInterestProvider",
    "CompatOrderbookProvider",
    "RedisIndicatorsProvider",
]
