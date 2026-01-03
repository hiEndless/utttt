"""
提供封装与保存专家 Agent 产出物的系统层能力，结构为：
- _context_meta ：来自 AGENT_REGISTRY 的合约元信息
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
        "role": AGENT_REGISTRY[a]["role"],
        "scope": AGENT_REGISTRY[a]["scope"],
        "uses_crowd_state": AGENT_REGISTRY[a]["uses_crowd_state"],
    }


def wrap_agent_output(agent: str, output: Dict[str, Any], exchange: Optional[str] = None,
                      symbol: Optional[str] = None) -> Dict[str, Any]:
    meta = build_meta(agent)
    if exchange is not None:
        meta["exchange"] = exchange
    if symbol is not None:
        meta["symbol"] = symbol
    return {"_context_meta": meta, "agent_output": output or {}}


def compute_stream_key(agent: str, exchange: str, symbol: str) -> str:
    a = agent.lower()
    return f"agent_output:{exchange}:{symbol}:{a}:stream"


def compute_latest_key(agent: str, exchange: str, symbol: str) -> str:
    a = agent.lower()
    return f"agent_output:{exchange}:{symbol}:{a}:latest"


async def save_agent_output(agent: str, exchange: str, symbol: str, ts: int, output: Dict[str, Any]) -> Dict[str, Any]:
    from agent_server.utils.redis_client import RedisClient

    payload = wrap_agent_output(agent, output, exchange=exchange, symbol=symbol)
    rc = RedisClient()
    sk = compute_stream_key(agent, exchange, symbol)
    lk = compute_latest_key(agent, exchange, symbol)
    await rc.xadd_json(sk, payload, ts=ts)
    await rc.set_json(lk, payload)
    return payload


async def read_latest(agent: str, exchange: str, symbol: str) -> Optional[Dict[str, Any]]:
    from agent_server.utils.redis_client import RedisClient

    rc = RedisClient()
    lk = compute_latest_key(agent, exchange, symbol)
    v = await rc.get(lk)
    try:
        return json.loads(v or "{}") if v else None
    except Exception:
        return None
