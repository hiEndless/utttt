"""
提供封装与保存专家 Agent 产出物的系统层能力，结构为：
- _context_meta ：用于标识数据来源的最小元信息
- agent_output ：专家 Agent 的原始 JSON 产出物
{
"_context_meta": { ... },
"agent_output": { ... }
}
"""

from typing import Any, Dict, Optional
import json

from .registry import AGENT_REGISTRY


def build_meta(agent: str) -> Dict[str, Any]:
    a = agent.lower()
    if a not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {agent}")
    return {
        "agent": a,
    }


def wrap_agent_output(agent: str, output: Dict[str, Any], exchange: Optional[str] = None,
                      symbol: Optional[str] = None, ts: Optional[int] = None, event_id: Optional[str] = None) -> Dict[str, Any]:
    meta = build_meta(agent)
    if exchange is not None:
        meta["exchange"] = exchange
    if symbol is not None:
        meta["symbol"] = symbol
    if ts is not None:
        meta["ts"] = ts
    if event_id is not None:
        meta["event_id"] = event_id
    return {"_context_meta": meta, "agent_output": output or {}}


def compute_stream_key(agent: str, exchange: str, symbol: str, trade_id: str) -> str:
    a = agent.lower()
    return f"agent_output:{exchange}:{symbol}:{trade_id}:{a}:stream"


def compute_latest_key(agent: str, exchange: str, symbol: str, trade_id: str) -> str:
    a = agent.lower()
    return f"agent_output:{exchange}:{symbol}:{trade_id}:{a}:latest"


async def save_agent_output(
    agent: str,
    exchange: str,
    symbol: str,
    ts: int,
    output: Dict[str, Any],
    *,
    trade_id: str | list[str] | None = None,
    event_id: Optional[str] = None,
    model_id: Optional[str] = None,
) -> Dict[str, Any]:
    from agent_server.utils.redis_client import RedisClient
    from agent_server.utils.trade_event_recorder import get_recorder

    payload = wrap_agent_output(agent, output, exchange=exchange, symbol=symbol, ts=ts, event_id=event_id)
    # print(payload)

    rc = RedisClient()
    # 中文注释：下游存储兼容 trade_id 字符串或字符串列表；列表情况下按每个 trade_id 分别存储
    trade_ids: list[str]
    if isinstance(trade_id, list):
        trade_ids = [str(t).strip() for t in trade_id if str(t).strip()]
    elif isinstance(trade_id, str) and trade_id.strip():
        trade_ids = [trade_id.strip()]
    else:
        trade_ids = ["default"]

    first_payload: Dict[str, Any] | None = None
    for tid in trade_ids:
        # 交易输出按 trade_id 隔离，避免同交易对的不同交易互相覆盖 latest/stream
        sk = compute_stream_key(agent, exchange, symbol, trade_id=tid)
        lk = compute_latest_key(agent, exchange, symbol, trade_id=tid)
        await rc.xadd_json(sk, payload, ts=ts)
        await rc.set_json(lk, payload)
        if first_payload is None:
            first_payload = payload

    # 异步保存到数据库
    if event_id:
        for tid in trade_ids:
            try:
                recorder = get_recorder()
                await recorder.save_agent_analysis(
                    event_id=event_id,
                    model_version=model_id,
                    agent_name=agent,
                    analysis_data=output,
                    trade_id=tid,
                    exchange=exchange,
                    symbol=symbol
                )
            except Exception as e:
                # 记录日志但不阻断主流程
                print(f"Warning: 存储 Agent 分析结果失败: {e}")

    return first_payload or payload


async def read_latest(agent: str, exchange: str, symbol: str, trade_id: str) -> Optional[Dict[str, Any]]:
    from agent_server.utils.redis_client import RedisClient

    rc = RedisClient()
    lk = compute_latest_key(agent, exchange, symbol, trade_id=trade_id)
    v = await rc.get(lk)
    try:
        return json.loads(v or "{}") if v else None
    except Exception:
        return None
