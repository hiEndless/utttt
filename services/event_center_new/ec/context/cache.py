from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from ..contracts import EventContextSnapshot


class ContextSnapshotCache(Protocol):
    def get(self, asset: str) -> EventContextSnapshot | None:
        ...

    def set(self, asset: str, ctx: EventContextSnapshot, ttl_ms: int) -> None:
        ...


@dataclass
class _CacheItem:
    ctx: EventContextSnapshot
    expire_at: float


class InMemoryContextSnapshotCache:
    def __init__(self) -> None:
        self._items: dict[str, _CacheItem] = {}

    def get(self, asset: str) -> EventContextSnapshot | None:
        item = self._items.get(asset)
        if item is None:
            return None
        if time.time() >= item.expire_at:
            self._items.pop(asset, None)
            return None
        return item.ctx

    def set(self, asset: str, ctx: EventContextSnapshot, ttl_ms: int) -> None:
        ttl_s = max(0.0, ttl_ms / 1000.0)
        self._items[asset] = _CacheItem(ctx=ctx, expire_at=time.time() + ttl_s)
