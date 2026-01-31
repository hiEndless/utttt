# build_agent_context 核心实现
# agent_context/builder.py
from typing import Any, Dict
import json

from .utils.path import delete_by_path
from .profiles import get_forbidden_paths
from .validators import validate_agent
from .registry import AGENT_REGISTRY



def _drop_internal_fields(ms: Dict[str, Any]) -> None:
    for _, v in (ms.get("market_state") or {}).items():
        if isinstance(v, dict):
            v.pop("_raw_trends", None)


def build_agent_context(
        agent: str,
        full_context: Dict[str, Any],
) -> Dict[str, Any]:
    agent = agent.lower()
    validate_agent(agent)

    # fusion 拿 full
    if agent == "fusion":
        ctx = json.loads(json.dumps(full_context))
        _drop_internal_fields(ctx)
        ctx["_context_meta"] = AGENT_REGISTRY[agent]
        return ctx

    forbidden_paths = get_forbidden_paths(agent)

    out: Dict[str, Any] = json.loads(json.dumps(full_context or {}))
    if out.get("symbol") is None:
        out["symbol"] = (full_context or {}).get("symbol")
    if out.get("ts") is None:
        out["ts"] = (full_context or {}).get("ts")

    for path in forbidden_paths:
        delete_by_path(out, path)

    _drop_internal_fields(out)

    return out
    
