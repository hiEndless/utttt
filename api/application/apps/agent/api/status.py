from __future__ import annotations

import json
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from tortoise.expressions import Q

from ...account.auth import get_current_user_id
from ...settings.models import SystemPreference, AgentModelConfig
from ....common.redis_client import get_async_redis_client
from ....common.status_codes import BaseResponse, StatusCode, BusinessException, success_response


router = APIRouter(tags=["Agent - Runtime"])

REQUIRED_AGENT_NAMES: tuple[str, ...] = (
    "kline",
    "human_market_narrator",
    "signal_validation",
    "decision",
    "position_risk",
    "market_structure",
    "trade_behavior",
)


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


async def _compute_agent_config_readiness(*, user_id: str) -> tuple[bool, list[str], list[str]]:
    required = list(REQUIRED_AGENT_NAMES)
    configs = (
        await AgentModelConfig.filter(
            deleted_at__isnull=True,
            is_active=True,
            provider__deleted_at__isnull=True,
            provider__is_active=True,
        )
        .filter(Q(user_id=user_id) | Q(user_id=None))
        .filter(Q(provider__user_id=user_id) | Q(provider__user_id=None))
        .prefetch_related("provider")
        .order_by("-updated_at")
    )

    best: dict[str, AgentModelConfig] = {}
    for cfg in configs:
        name = str(cfg.agent_name or "").strip()
        if not name or name not in required:
            continue
        cur = best.get(name)
        if cur is None:
            best[name] = cfg
            continue
        cur_uid = str(cur.user_id) if cur.user_id is not None else None
        cfg_uid = str(cfg.user_id) if cfg.user_id is not None else None
        if cur_uid is None and cfg_uid is not None:
            best[name] = cfg
            continue
        if cur_uid == cfg_uid and cfg.updated_at > cur.updated_at:
            best[name] = cfg

    reasons: list[str] = []
    missing_cfg = [a for a in required if a not in best]
    if missing_cfg:
        reasons.append(f"missing_agent_model_configs:{','.join(missing_cfg)}")

    model_missing: list[str] = []
    base_url_missing: list[str] = []
    api_key_missing: list[str] = []
    for a in required:
        cfg = best.get(a)
        if not cfg:
            continue
        if not str(cfg.model_id or "").strip():
            model_missing.append(a)
        provider = cfg.provider
        if not str(getattr(provider, "base_url", "") or "").strip():
            base_url_missing.append(a)
        if not str(getattr(provider, "api_key", "") or "").strip():
            api_key_missing.append(a)

    if model_missing:
        reasons.append(f"missing_model_id:{','.join(model_missing)}")
    if base_url_missing:
        reasons.append(f"missing_llm_base_url:{','.join(base_url_missing)}")
    if api_key_missing:
        reasons.append(f"missing_llm_api_key:{','.join(api_key_missing)}")

    return len(reasons) == 0, reasons, required


class AgentStatusOut(BaseModel):
    status_source: str
    alive: bool
    enabled: bool
    ready: bool
    reasons: list[str] = Field(default_factory=list)
    config_ready: bool
    config_reasons: list[str] = Field(default_factory=list)
    config_required_agents: list[str] = Field(default_factory=list)
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
    raw_user = await redis.hgetall(key_user)
    raw_global = None
    status_source = "none"
    raw = raw_user
    if raw_user:
        status_source = "user"
    else:
        raw_global = await redis.hgetall(key_global)
        raw = raw_global
        if raw_global:
            status_source = "global"

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

    try:
        config_ready, config_reasons, config_required_agents = await _compute_agent_config_readiness(user_id=user_id)
    except Exception:
        config_ready, config_reasons, config_required_agents = False, ["config_check_failed"], list(REQUIRED_AGENT_NAMES)

    return success_response(AgentStatusOut(
        status_source=status_source,
        alive=alive,
        enabled=enabled,
        ready=ready,
        reasons=reasons,
        config_ready=config_ready,
        config_reasons=config_reasons,
        config_required_agents=config_required_agents,
        last_ts=last_ts,
        modules=modules,
    ))
