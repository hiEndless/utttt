from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...account.auth import get_current_user_id
from ...settings.models import SystemPreference
from ....common.status_codes import BaseResponse, StatusCode, BusinessException, success_response


router = APIRouter(tags=["Agent - Runtime"])


def _coerce_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (str, int, float, bool)):
        return {"value": value}
    return {"value": str(value)}


class AgentEnabledIn(BaseModel):
    enabled: bool = Field(...)


class AgentEnabledOut(BaseModel):
    enabled: bool


@router.post("/agent/enabled", response_model=BaseResponse[AgentEnabledOut])
async def set_agent_enabled(
    body: AgentEnabledIn,
    user_id: str = Depends(get_current_user_id),
):
    """
    中文说明：设置当前用户的 Agent 总开关（写入 system_preferences.agent_enabled）。
    """
    existing = await SystemPreference.get_or_none(user_id=user_id, key="agent_enabled")
    if existing:
        existing.value = _coerce_json_value(bool(body.enabled))
        await existing.save()
    else:
        await SystemPreference.create(
            user_id=user_id,
            key="agent_enabled",
            value=_coerce_json_value(bool(body.enabled)),
        )

    return success_response(AgentEnabledOut(enabled=bool(body.enabled)))

