from __future__ import annotations

import json
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...account.auth import get_current_user_id
from ...settings.models import SystemPreference
from ....common.redis_client import get_async_redis_client
from ....common.status_codes import BaseResponse, StatusCode, BusinessException, success_response


router = APIRouter(tags=["Agent - Runtime"])


def _coerce_pref_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, dict):
        for k in ("value", "enabled", "on"):
            if k in value:
                return _coerce_pref_bool(value.get(k))
        return None
    s = str(value).strip()
    if not s:
        return None
    low = s.lower()
    if low in ("true", "1", "yes", "y", "on"):
        return True
    if low in ("false", "0", "no", "n", "off"):
        return False
    return None


def _safe_json_loads(s: Any) -> dict[str, Any]:
    if not s:
        return {}
    if isinstance(s, dict):
        return s
    try:
        return json.loads(str(s))
    except Exception:
        return {}


class AgentStatusOut(BaseModel):
    alive: bool
    enabled: bool
    ready: bool
    reasons: list[str] = Field(default_factory=list)
    last_ts: Optional[int] = None
    modules: dict[str, Any] = Field(default_factory=dict)


@router.get("/agent/status", response_model=BaseResponse[AgentStatusOut])
async def get_agent_status(user_id: str = Depends(get_current_user_id)):
    """
    中文说明：读取 agent_server 写入 Redis 的心跳/就绪态，并补充当前用户的 agent_enabled 偏好。
    """
    pref = await SystemPreference.get_or_none(user_id=user_id, key="agent_enabled")
    enabled_pref = _coerce_pref_bool(pref.value if pref else None)
    enabled = bool(enabled_pref) if enabled_pref is not None else False

    redis = get_async_redis_client()
    key_user = f"agent:status:{user_id}"
    key_global = "agent:status:global"
    raw = await redis.hgetall(key_user)
    if not raw:
        raw = await redis.hgetall(key_global)

    now_ms = int(time.time() * 1000)
    modules: dict[str, Any] = {}
    last_ts: Optional[int] = None
    ready = False
    reasons: list[str] = []
    for module, payload in (raw or {}).items():
        obj = _safe_json_loads(payload)
        modules[module] = obj
        ts = obj.get("ts")
        if isinstance(ts, (int, float)):
            ts_i = int(ts)
            if last_ts is None or ts_i > last_ts:
                last_ts = ts_i
        if module == "final_listener":
            ready = bool(obj.get("ready"))
            reasons = list(obj.get("reasons") or [])

    alive = bool(last_ts is not None and (now_ms - last_ts) <= 15_000)
    if raw and not reasons:
        for module, obj in modules.items():
            if isinstance(obj, dict) and obj.get("reasons"):
                reasons = list(obj.get("reasons") or [])
                ready = bool(obj.get("ready"))
                break

    return success_response(AgentStatusOut(
        alive=alive,
        enabled=enabled,
        ready=ready,
        reasons=reasons,
        last_ts=last_ts,
        modules=modules,
    ))

