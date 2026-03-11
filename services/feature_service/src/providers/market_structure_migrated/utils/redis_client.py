from __future__ import annotations

from typing import Any

from api.application.common.redis_client import get_async_redis_client


def get_redis_client() -> Any:
    return get_async_redis_client()


async def get_verified_redis_client() -> Any:
    return get_async_redis_client()
