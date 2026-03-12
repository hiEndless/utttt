from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Dict

from services.feature_service.src.ports.news_provider import NewsProvider
from services.feature_service.src.ports.onchain_provider import OnchainProvider
from services.feature_service.src.ports.social_provider import SocialProvider
from services.feature_service.src.providers.degradation_state import mark_degraded

logger = logging.getLogger(__name__)


def _normalize_source_payload(
    *,
    source_type: str,
    payload: Dict[str, Any] | None,
    provider_state: str,
) -> Dict[str, Any]:
    raw = dict(payload or {})
    has_envelope = any(k in raw for k in ("source_type", "features", "provider_state", "available", "as_of_ms"))
    if has_envelope:
        features = raw.get("features")
        if not isinstance(features, dict):
            features = {}
        available = bool(raw.get("available")) if "available" in raw else bool(features)
        as_of_ms = raw.get("as_of_ms")
        state = str(raw.get("provider_state") or provider_state)
    else:
        features = raw
        available = bool(features)
        as_of_ms = None
        state = provider_state if available else "empty"
    return {
        "source_type": source_type,
        "available": available,
        "provider_state": state,
        "as_of_ms": as_of_ms,
        "features": features,
    }


def _reserved_unavailable_payload(source_type: str, *, provider_state: str) -> Dict[str, Any]:
    return _normalize_source_payload(
        source_type=source_type,
        payload={"features": {}, "available": False, "as_of_ms": None},
        provider_state=provider_state,
    )


class NoopNewsProvider(NewsProvider):
    async def get_news_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return _reserved_unavailable_payload("news", provider_state="noop")


class NoopSocialProvider(SocialProvider):
    async def get_social_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return _reserved_unavailable_payload("social", provider_state="noop")


class NoopOnchainProvider(OnchainProvider):
    async def get_onchain_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return _reserved_unavailable_payload("onchain", provider_state="noop")


class StaticNewsProvider(NewsProvider):
    def __init__(self, payload: Dict[str, Any] | None = None) -> None:
        self._payload = dict(payload or {})

    async def get_news_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return _normalize_source_payload(
            source_type="news",
            payload=deepcopy(self._payload),
            provider_state="static",
        )


class StaticSocialProvider(SocialProvider):
    def __init__(self, payload: Dict[str, Any] | None = None) -> None:
        self._payload = dict(payload or {})

    async def get_social_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return _normalize_source_payload(
            source_type="social",
            payload=deepcopy(self._payload),
            provider_state="static",
        )


class StaticOnchainProvider(OnchainProvider):
    def __init__(self, payload: Dict[str, Any] | None = None) -> None:
        self._payload = dict(payload or {})

    async def get_onchain_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return _normalize_source_payload(
            source_type="onchain",
            payload=deepcopy(self._payload),
            provider_state="static",
        )


class FallbackNewsProvider(NewsProvider):
    def __init__(self, primary: NewsProvider, fallback: NewsProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def get_news_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        try:
            return _normalize_source_payload(
                source_type="news",
                payload=dict(await self._primary.get_news_features(exchange, symbol) or {}),
                provider_state="primary",
            )
        except Exception:
            mark_degraded("news_provider_fallback")
            logger.warning(
                "新闻特征主Provider失败，已降级到备用Provider exchange=%s symbol=%s",
                exchange,
                symbol,
                exc_info=True,
            )
            return _normalize_source_payload(
                source_type="news",
                payload=dict(await self._fallback.get_news_features(exchange, symbol) or {}),
                provider_state="fallback",
            )


class FallbackSocialProvider(SocialProvider):
    def __init__(self, primary: SocialProvider, fallback: SocialProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def get_social_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        try:
            return _normalize_source_payload(
                source_type="social",
                payload=dict(await self._primary.get_social_features(exchange, symbol) or {}),
                provider_state="primary",
            )
        except Exception:
            mark_degraded("social_provider_fallback")
            logger.warning(
                "社交特征主Provider失败，已降级到备用Provider exchange=%s symbol=%s",
                exchange,
                symbol,
                exc_info=True,
            )
            return _normalize_source_payload(
                source_type="social",
                payload=dict(await self._fallback.get_social_features(exchange, symbol) or {}),
                provider_state="fallback",
            )


class FallbackOnchainProvider(OnchainProvider):
    def __init__(self, primary: OnchainProvider, fallback: OnchainProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def get_onchain_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        try:
            return _normalize_source_payload(
                source_type="onchain",
                payload=dict(await self._primary.get_onchain_features(exchange, symbol) or {}),
                provider_state="primary",
            )
        except Exception:
            mark_degraded("onchain_provider_fallback")
            logger.warning(
                "链上特征主Provider失败，已降级到备用Provider exchange=%s symbol=%s",
                exchange,
                symbol,
                exc_info=True,
            )
            return _normalize_source_payload(
                source_type="onchain",
                payload=dict(await self._fallback.get_onchain_features(exchange, symbol) or {}),
                provider_state="fallback",
            )


class UnavailableNewsProvider(NewsProvider):
    async def get_news_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        mark_degraded("news_provider_unavailable")
        return _reserved_unavailable_payload("news", provider_state="unavailable")


class UnavailableSocialProvider(SocialProvider):
    async def get_social_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        mark_degraded("social_provider_unavailable")
        return _reserved_unavailable_payload("social", provider_state="unavailable")


class UnavailableOnchainProvider(OnchainProvider):
    async def get_onchain_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        mark_degraded("onchain_provider_unavailable")
        return _reserved_unavailable_payload("onchain", provider_state="unavailable")
