from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from redis.asyncio import Redis


@dataclass
class InMemoryIdempotencyStore:
    """进程内幂等缓存（开发/测试用）。"""

    store: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    locks: set[str] = field(default_factory=set)

    async def get_result(self, decision_id: str) -> Optional[Dict[str, Any]]:
        out = self.store.get(str(decision_id))
        return None if out is None else dict(out)

    async def save_result(self, decision_id: str, result: Dict[str, Any]) -> None:
        self.store[str(decision_id)] = dict(result or {})

    async def try_acquire_lock(self, decision_id: str, ttl_s: int) -> bool:
        _ = ttl_s
        key = str(decision_id)
        if key in self.locks:
            return False
        self.locks.add(key)
        return True

    async def release_lock(self, decision_id: str) -> None:
        self.locks.discard(str(decision_id))


@dataclass
class RedisIdempotencyStore:
    """基于 Redis 的幂等缓存。"""

    redis_client: Redis
    key_template: str = "execution:idempotency:{decision_id}"
    ttl_s: int = 3600
    lock_key_template: str = "execution:idempotency:lock:{decision_id}"

    async def get_result(self, decision_id: str) -> Optional[Dict[str, Any]]:
        key = self.key_template.format(decision_id=str(decision_id))
        raw = await self.redis_client.get(key)
        if not isinstance(raw, str) or not raw.strip():
            return None
        try:
            parsed = json.loads(raw)
        except Exception:
            return None
        return dict(parsed) if isinstance(parsed, dict) else None

    async def save_result(self, decision_id: str, result: Dict[str, Any]) -> None:
        key = self.key_template.format(decision_id=str(decision_id))
        payload = json.dumps(result or {}, ensure_ascii=False)
        await self.redis_client.set(key, payload, ex=int(self.ttl_s))

    async def try_acquire_lock(self, decision_id: str, ttl_s: int) -> bool:
        key = self.lock_key_template.format(decision_id=str(decision_id))
        ok = await self.redis_client.set(key, "1", nx=True, ex=int(ttl_s))
        return bool(ok)

    async def release_lock(self, decision_id: str) -> None:
        key = self.lock_key_template.format(decision_id=str(decision_id))
        await self.redis_client.delete(key)
