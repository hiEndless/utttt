from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Dict

from feature_service.ports.news_provider import NewsProvider
from feature_service.ports.onchain_provider import OnchainProvider
from feature_service.ports.social_provider import SocialProvider
from feature_service.providers.degradation_state import mark_degraded

logger = logging.getLogger(__name__)


class NoopNewsProvider(NewsProvider):
    async def get_news_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return {}


class NoopSocialProvider(SocialProvider):
    async def get_social_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return {}


class NoopOnchainProvider(OnchainProvider):
    async def get_onchain_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return {}


class StaticNewsProvider(NewsProvider):
    def __init__(self, payload: Dict[str, Any] | None = None) -> None:
        self._payload = dict(payload or {})

    async def get_news_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return deepcopy(self._payload)


class StaticSocialProvider(SocialProvider):
    def __init__(self, payload: Dict[str, Any] | None = None) -> None:
        self._payload = dict(payload or {})

    async def get_social_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return deepcopy(self._payload)


class StaticOnchainProvider(OnchainProvider):
    def __init__(self, payload: Dict[str, Any] | None = None) -> None:
        self._payload = dict(payload or {})

    async def get_onchain_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return deepcopy(self._payload)


class FallbackNewsProvider(NewsProvider):
    def __init__(self, primary: NewsProvider, fallback: NewsProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def get_news_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        try:
            return dict(await self._primary.get_news_features(exchange, symbol) or {})
        except Exception:
            mark_degraded("news_provider_fallback")
            logger.warning(
                "新闻特征主Provider失败，已降级到备用Provider exchange=%s symbol=%s",
                exchange,
                symbol,
                exc_info=True,
            )
            return dict(await self._fallback.get_news_features(exchange, symbol) or {})


class FallbackSocialProvider(SocialProvider):
    def __init__(self, primary: SocialProvider, fallback: SocialProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def get_social_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        try:
            return dict(await self._primary.get_social_features(exchange, symbol) or {})
        except Exception:
            mark_degraded("social_provider_fallback")
            logger.warning(
                "社交特征主Provider失败，已降级到备用Provider exchange=%s symbol=%s",
                exchange,
                symbol,
                exc_info=True,
            )
            return dict(await self._fallback.get_social_features(exchange, symbol) or {})


class FallbackOnchainProvider(OnchainProvider):
    def __init__(self, primary: OnchainProvider, fallback: OnchainProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def get_onchain_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        try:
            return dict(await self._primary.get_onchain_features(exchange, symbol) or {})
        except Exception:
            mark_degraded("onchain_provider_fallback")
            logger.warning(
                "链上特征主Provider失败，已降级到备用Provider exchange=%s symbol=%s",
                exchange,
                symbol,
                exc_info=True,
            )
            return dict(await self._fallback.get_onchain_features(exchange, symbol) or {})


class UnavailableNewsProvider(NewsProvider):
    async def get_news_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        mark_degraded("news_provider_unavailable")
        return {}


class UnavailableSocialProvider(SocialProvider):
    async def get_social_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        mark_degraded("social_provider_unavailable")
        return {}


class UnavailableOnchainProvider(OnchainProvider):
    async def get_onchain_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        mark_degraded("onchain_provider_unavailable")
        return {}
