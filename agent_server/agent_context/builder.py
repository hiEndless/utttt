# build_agent_context 核心实现
# agent_context/builder.py
from typing import Any, Dict
import json

from .utils import get_by_path, set_by_path
from .profiles import get_allowed_paths
from .validators import validate_agent, forbid_full_context
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

    paths = get_allowed_paths(agent)
    if not paths:
        forbid_full_context(agent)

    out: Dict[str, Any] = {
        "symbol": full_context.get("symbol"),
        "ts": full_context.get("ts"),
    }

    for path in paths:
        val = get_by_path(full_context, path)
        if val is not None:
            set_by_path(out, path, val)

    _drop_internal_fields(out)

    return out
    