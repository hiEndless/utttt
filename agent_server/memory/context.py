import json
from typing import Any, Dict

from .store import MemoryStore


async def get_agent_context(trade_id: str, current_event: Dict[str, Any], role: str, role_specific: Dict[str, Any]) -> Dict[str, Any]:
    store = MemoryStore()
    ctx = await store.get_model_context(trade_id)
    return {
        "latest_summary": ctx.get("latest_summary") or "",
        "state": ctx.get("state") or {},
        "context_slices": ctx.get("context_slices") or [],
        "current_event": current_event or {},
        "agent_specific": {"role": role, **(role_specific or {})},
    }


async def assemble_text_prompt(trade_id: str, current_event: Dict[str, Any], role: str, role_specific: Dict[str, Any]) -> str:
    obj = await get_agent_context(trade_id, current_event, role, role_specific)
    parts = []
    parts.append("latest_summary:\n" + (obj.get("latest_summary") or ""))
    parts.append("state:\n" + json.dumps(obj.get("state") or {}, ensure_ascii=False))
    parts.append("context_slices:\n" + json.dumps(obj.get("context_slices") or [], ensure_ascii=False))
    parts.append("current_event:\n" + json.dumps(obj.get("current_event") or {}, ensure_ascii=False))
    parts.append("agent_specific:\n" + json.dumps(obj.get("agent_specific") or {}, ensure_ascii=False))
    return "\n\n".join(parts)