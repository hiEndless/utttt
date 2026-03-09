from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...account.views import get_current_user_id
from ..models import AgentAnalysis, Trade, TradeEvent
from ....common.status_codes import BaseResponse, BusinessException, StatusCode, success_response

router = APIRouter(tags=["Dashboard - Agent Analyses"])


IncludeMode = Literal["summary", "full"]


class AgentAnalysisItem(BaseModel):
    # 中文注释：用于“一个事件下某个 Agent 的最新分析概览”，满足前端列表快速展示。
    agent_name: str
    model_version: Optional[str] = None
    risk_action: Optional[str] = None
    mark_price: Optional[str] = None
    market_accuracy: Optional[str] = None
    decision_quality: Optional[str] = None
    created_at: str

    reasoning: Optional[Any] = None
    full_output: Optional[Any] = None
    execution_state: Optional[Any] = None
    global_state: Optional[Any] = None


class EventAnalysisResponse(BaseModel):
    # 中文注释：trade_events.event_id（业务字符串） + trade_events.id（PK）一起返回，便于排查映射问题。
    event_id: str
    event_pk: int
    event_type: str
    event_at: int
    agents: List[AgentAnalysisItem]


class BatchEventAnalysesRequest(BaseModel):
    event_ids: List[str] = Field(..., min_length=1, description="事件业务 ID 列表（trade_events.event_id）")
    latest_per_agent: bool = Field(True, description="同一事件同一 agent 仅返回最新一条")
    include: IncludeMode = Field("summary", description="summary 仅返回概览；full 额外返回大字段")


class BatchEventAnalysesItem(BaseModel):
    event_id: str
    found: bool
    event_pk: Optional[int] = None
    agents: List[AgentAnalysisItem] = Field(default_factory=list)


def _to_analysis_item(a: AgentAnalysis, include: IncludeMode) -> AgentAnalysisItem:
    # 中文注释：Decimal/Datetime 等类型统一转为前端友好的字符串，避免 JSON 序列化差异。
    created_at = a.created_at.isoformat() if getattr(a, "created_at", None) else ""
    item = AgentAnalysisItem(
        agent_name=str(a.agent_name),
        model_version=str(a.model_version) if a.model_version is not None else None,
        risk_action=str(a.risk_action) if a.risk_action is not None else None,
        mark_price=str(a.mark_price) if a.mark_price is not None else None,
        market_accuracy=str(a.market_accuracy) if a.market_accuracy is not None else None,
        decision_quality=str(a.decision_quality) if a.decision_quality is not None else None,
        created_at=created_at,
    )
    if include == "full":
        item.reasoning = a.reasoning
        item.full_output = a.full_output
        item.execution_state = a.execution_state
        item.global_state = a.global_state
    return item


def _reduce_latest_per_agent(items: List[AgentAnalysisItem]) -> List[AgentAnalysisItem]:
    # 中文注释：按 created_at（已按 desc 排序）保留每个 agent 的第一条，即最新记录。
    seen: set[str] = set()
    out: List[AgentAnalysisItem] = []
    for it in items:
        if it.agent_name in seen:
            continue
        seen.add(it.agent_name)
        out.append(it)
    out.sort(key=lambda x: x.agent_name)
    return out


async def _ensure_trade_owner(trade_id: str, user_id: str) -> Trade:
    # 中文注释：复用 trade_events.py 的鉴权策略：trade 必须属于当前用户，否则返回 404（避免越权探测）。
    trade = await Trade.get_or_none(trade=trade_id, user_id=user_id)
    if not trade:
        raise BusinessException(code=StatusCode.NOT_FOUND, message=f"trade {trade_id} 不存在或无权限访问")
    return trade


async def _get_latest_trade_event_pk(trade_id: str, event_id: str) -> Optional[Tuple[int, TradeEvent]]:
    # 中文注释：同一 trade_id + event_id 可能对应多条事件记录（历史/重复落库）；默认取 event_at 最新的一条。
    e = (
        await TradeEvent.filter(trade__trade=trade_id, event_id=event_id)
        .order_by("-event_at")
        .first()
    )
    if not e:
        return None
    return int(e.id), e


@router.get(
    "/dashboard/trades/{trade_id}/events/{event_id}/analyses",
    response_model=BaseResponse[EventAnalysisResponse],
)
async def get_event_analyses(
    trade_id: str,
    event_id: str,
    latest_per_agent: bool = True,
    include: IncludeMode = "summary",
    user_id: str = Depends(get_current_user_id),
):
    """
    查询某笔交易中“某个事件（业务 event_id）”对应的 Agent 分析结果

    - 前端提交：trade_id + event_id（业务字符串）
    - 后端内部：定位 trade_events 记录后，用其 PK（trade_events.id）查询 agent_analyses.event_id
    """
    trade_id = (trade_id or "").strip()
    event_id = (event_id or "").strip()
    if not trade_id:
        raise BusinessException(code=StatusCode.PARAM_ERROR, message="trade_id 不能为空")
    if not event_id:
        raise BusinessException(code=StatusCode.PARAM_ERROR, message="event_id 不能为空")

    await _ensure_trade_owner(trade_id=trade_id, user_id=user_id)

    resolved = await _get_latest_trade_event_pk(trade_id=trade_id, event_id=event_id)
    if not resolved:
        raise BusinessException(code=StatusCode.NOT_FOUND, message=f"event {event_id} 不存在或无权限访问")
    event_pk, e = resolved

    analyses_db = await AgentAnalysis.filter(event_id=event_pk, user_id=user_id).order_by("-created_at")
    items = [_to_analysis_item(a, include=include) for a in analyses_db]
    if latest_per_agent:
        items = _reduce_latest_per_agent(items)

    resp = EventAnalysisResponse(
        event_id=str(e.event_id),
        event_pk=int(event_pk),
        event_type=str(e.event_type),
        event_at=int(e.event_at),
        agents=items,
    )
    return success_response(resp)


@router.post(
    "/dashboard/trades/{trade_id}/events/analyses:batch",
    response_model=BaseResponse[List[BatchEventAnalysesItem]],
)
async def batch_get_event_analyses(
    trade_id: str,
    payload: BatchEventAnalysesRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    批量查询某笔交易中多个事件的 Agent 分析结果

    - 适用场景：前端点击某根 K 线后返回多个事件点，建议一次批量拉取并缓存，避免按钮切换时频繁请求。
    """
    trade_id = (trade_id or "").strip()
    if not trade_id:
        raise BusinessException(code=StatusCode.PARAM_ERROR, message="trade_id 不能为空")

    await _ensure_trade_owner(trade_id=trade_id, user_id=user_id)

    # 中文注释：先拉取该 trade 下所有命中的事件记录（可能同 event_id 多条），后续按 event_at 取最新。
    target_event_ids = [e.strip() for e in payload.event_ids if isinstance(e, str) and e.strip()]
    if not target_event_ids:
        raise BusinessException(code=StatusCode.PARAM_ERROR, message="event_ids 不能为空")

    event_rows = (
        await TradeEvent.filter(trade__trade=trade_id, event_id__in=target_event_ids)
        .order_by("-event_at")
        .all()
    )

    latest_event_by_event_id: Dict[str, TradeEvent] = {}
    for e in event_rows:
        key = str(e.event_id)
        if key not in latest_event_by_event_id:
            latest_event_by_event_id[key] = e

    event_pks = [int(e.id) for e in latest_event_by_event_id.values()]
    analyses_by_event_pk: Dict[int, List[AgentAnalysisItem]] = {}
    if event_pks:
        analyses_db = (
            await AgentAnalysis.filter(event_id__in=event_pks, user_id=user_id)
            .order_by("event_id", "-created_at")
            .all()
        )
        for a in analyses_db:
            pk = int(a.event_id)
            analyses_by_event_pk.setdefault(pk, []).append(_to_analysis_item(a, include=payload.include))

    items: List[BatchEventAnalysesItem] = []
    for event_id in payload.event_ids:
        key = event_id.strip() if isinstance(event_id, str) else ""
        if not key:
            continue
        e = latest_event_by_event_id.get(key)
        if not e:
            items.append(BatchEventAnalysesItem(event_id=key, found=False, event_pk=None, agents=[]))
            continue
        pk = int(e.id)
        agents = analyses_by_event_pk.get(pk, [])
        if payload.latest_per_agent:
            agents = _reduce_latest_per_agent(agents)
        items.append(BatchEventAnalysesItem(event_id=key, found=True, event_pk=pk, agents=agents))

    return success_response(items)
