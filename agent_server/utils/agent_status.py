from __future__ import annotations

import json
import time
from typing import Any, Optional

import redis.asyncio as aioredis

from agent_server.configs.source import get_agent_enabled, get_agent_readiness


STATUS_KEY_PREFIX = "agent:status"
STATUS_TTL_SEC = 30


def _status_key(user_id: Optional[str]) -> str:
    uid = str(user_id or "").strip() or "global"
    return f"{STATUS_KEY_PREFIX}:{uid}"


async def update_agent_status(
    redis: aioredis.Redis,
    *,
    module: str,
    user_id: Optional[str],
    extra: Optional[dict[str, Any]] = None,
) -> None:
    enabled = get_agent_enabled(user_id=user_id)
    readiness = get_agent_readiness(user_id=user_id)
    await update_agent_status_snapshot(
        redis,
        module=module,
        user_id=user_id,
        enabled=enabled,
        ready=bool(readiness.get("ready")),
        reasons=list(readiness.get("reasons") or []),
        extra=extra,
    )


async def get_agent_gate_snapshot(*, user_id: Optional[str]) -> tuple[bool, bool, list[str]]:
    enabled = get_agent_enabled(user_id=user_id)
    readiness = get_agent_readiness(user_id=user_id)
    ready = bool(readiness.get("ready"))
    reasons = list(readiness.get("reasons") or [])
    return enabled, ready, reasons


async def update_agent_status_snapshot(
    redis: aioredis.Redis,
    *,
    module: str,
    user_id: Optional[str],
    enabled: bool,
    ready: bool,
    reasons: list[str],
    extra: Optional[dict[str, Any]] = None,
) -> None:
    payload: dict[str, Any] = {
        "ts": int(time.time() * 1000),
        "module": module,
        "enabled": enabled,
        "ready": ready,
        "reasons": reasons,
    }
    if extra:
        payload["extra"] = extra

    key = _status_key(user_id)
    await redis.hset(key, module, json.dumps(payload, ensure_ascii=False))
    await redis.expire(key, STATUS_TTL_SEC)
