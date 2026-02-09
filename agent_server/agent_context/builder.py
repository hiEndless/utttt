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

def _normalize_horizon_key(horizon: Any) -> str:
    hz = str(horizon or "").strip().lower()
    if hz in ("short", "short_term"):
        return "short_term"
    if hz in ("mid", "mid_term"):
        return "mid_term"
    if hz in ("long", "long_term"):
        return "long_term"
    return hz


def _crop_market_structure_by_horizon(agent: str, ctx: Dict[str, Any], horizon: Any) -> None:
    hz = _normalize_horizon_key(horizon)
    if not hz:
        return
    
    # 不同 agent 可单独配置“给定持仓周期 → 需要保留的周期桶”
    crop_config = {
        "signal_validation": {
            "short_term": ["short_term", "mid_term"],
            "mid_term": ["mid_term", "long_term"],
            "long_term": ["mid_term", "long_term"],
        },
        "decision": {
            "short_term": ["short_term", "mid_term"],
            "mid_term": ["mid_term", "long_term"],
            "long_term": ["mid_term", "long_term"],
        },
    }

    agent_cfg = crop_config.get(agent)
    if not isinstance(agent_cfg, dict):
        return

    allowed = agent_cfg.get(hz)
    if not isinstance(allowed, list) or not allowed:
        return

    pre = ctx.get("pre_decision_structure")
    if isinstance(pre, dict):
        ctx["pre_decision_structure"] = {k: v for k, v in pre.items() if k in allowed}

    ch = ctx.get("candidate_horizons")
    if isinstance(ch, list):
        ctx["candidate_horizons"] = [k for k in allowed if k in ch]


def build_agent_context(
        agent: str,
        full_context: Dict[str, Any],
        horizon: Any = None,
) -> Dict[str, Any]:
    agent = agent.lower()
    validate_agent(agent)

    forbidden_paths = get_forbidden_paths(agent)

    out: Dict[str, Any] = json.loads(json.dumps(full_context or {}))
    if out.get("symbol") is None:
        out["symbol"] = (full_context or {}).get("symbol")
    if out.get("ts") is None:
        out["ts"] = (full_context or {}).get("ts")

    for path in forbidden_paths:
        delete_by_path(out, path)

    _crop_market_structure_by_horizon(agent, out, horizon)
    _drop_internal_fields(out)

    return out
    
