from __future__ import annotations

from typing import Any, Dict


def route_signal_agent_key(*, signal_event: Dict[str, Any]) -> str:
    """按事件类型/来源类别路由信号决策 agent。"""
    payload = dict((signal_event or {}).get("payload") or {})
    event_type = str(payload.get("event_type") or payload.get("type") or payload.get("kind") or "").strip().lower()
    source_category = str(payload.get("source_category") or "").strip().lower()
    source_obj = payload.get("source")
    source_name = ""
    if isinstance(source_obj, dict):
        source_name = str(source_obj.get("name") or "").strip().lower()
        if not source_category:
            source_category = str(source_obj.get("category") or "").strip().lower()
    elif source_obj:
        source_name = str(source_obj).strip().lower()

    text = " ".join([event_type, source_category, source_name]).strip()
    if any(x in text for x in ("liquidation", "liq", "squeeze", "forced_liq")):
        return "liquidation"
    if any(x in text for x in ("onchain", "whale", "nansen", "glassnode", "arkham", "chain")):
        return "onchain"
    if any(x in text for x in ("news", "social", "macro", "twitter", "reddit", "coindesk", "reuters", "bloomberg")):
        return "social_news"
    if any(x in text for x in ("indicator", "technical", "signal", "strategy", "orderbook", "funding")):
        return "technical"
    return "generic"

