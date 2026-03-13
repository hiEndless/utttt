from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List


_DEFAULT_ROUTER_CONFIG = {
    "default_agent_key": "generic",
    "rules": [
        {"agent_key": "liquidation", "keywords": ["liquidation", "liq", "squeeze", "forced_liq"]},
        {"agent_key": "onchain", "keywords": ["onchain", "whale", "nansen", "glassnode", "arkham", "chain"]},
        {
            "agent_key": "social_news",
            "keywords": ["news", "social", "macro", "twitter", "reddit", "coindesk", "reuters", "bloomberg"],
        },
        {"agent_key": "technical", "keywords": ["indicator", "technical", "signal", "strategy", "orderbook", "funding"]},
    ],
}


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "signal_router_profiles.json"


@lru_cache(maxsize=8)
def _load_router_config(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return dict(_DEFAULT_ROUTER_CONFIG)
    try:
        parsed = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return dict(_DEFAULT_ROUTER_CONFIG)
    if not isinstance(parsed, dict):
        return dict(_DEFAULT_ROUTER_CONFIG)
    rules = parsed.get("rules")
    default_agent_key = str(parsed.get("default_agent_key") or "generic").strip().lower() or "generic"
    if not isinstance(rules, list):
        return {"default_agent_key": default_agent_key, "rules": list(_DEFAULT_ROUTER_CONFIG["rules"])}
    normalized_rules: List[Dict[str, Any]] = []
    for item in list(rules):
        if not isinstance(item, dict):
            continue
        agent_key = str(item.get("agent_key") or "").strip().lower()
        if not agent_key:
            continue
        keywords = [str(x).strip().lower() for x in list(item.get("keywords") or []) if str(x).strip()]
        if not keywords:
            continue
        normalized_rules.append({"agent_key": agent_key, "keywords": keywords})
    if not normalized_rules:
        normalized_rules = list(_DEFAULT_ROUTER_CONFIG["rules"])
    return {"default_agent_key": default_agent_key, "rules": normalized_rules}


def reset_signal_router_cache() -> None:
    _load_router_config.cache_clear()


def load_signal_router_config_from_env() -> Dict[str, Any]:
    raw = str(os.getenv("AGENT_SIGNAL_ROUTER_CONFIG_FILE", "") or "").strip()
    path = raw if raw else str(_default_config_path())
    return _load_router_config(path)


def validate_signal_router_config(
    cfg: Dict[str, Any],
    *,
    allowed_agent_keys: set[str] | None = None,
) -> None:
    """校验路由配置：空规则、未知 agent_key、重复关键词。"""
    if not isinstance(cfg, dict):
        raise ValueError("signal_router config 必须是对象")
    default_agent_key = str(cfg.get("default_agent_key") or "").strip().lower()
    if not default_agent_key:
        raise ValueError("signal_router.default_agent_key 不能为空")
    rules = cfg.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("signal_router.rules 必须是非空数组")
    allowed = set([x.strip().lower() for x in list(allowed_agent_keys or set()) if str(x).strip()])
    if allowed and default_agent_key not in allowed:
        raise ValueError(f"signal_router.default_agent_key 非法: {default_agent_key}")
    keyword_owner: Dict[str, str] = {}
    for idx, item in enumerate(list(rules)):
        if not isinstance(item, dict):
            raise ValueError(f"signal_router.rules[{idx}] 必须是对象")
        agent_key = str(item.get("agent_key") or "").strip().lower()
        if not agent_key:
            raise ValueError(f"signal_router.rules[{idx}].agent_key 不能为空")
        if allowed and agent_key not in allowed:
            raise ValueError(f"signal_router.rules[{idx}].agent_key 非法: {agent_key}")
        keywords = [str(x).strip().lower() for x in list(item.get("keywords") or []) if str(x).strip()]
        if not keywords:
            raise ValueError(f"signal_router.rules[{idx}].keywords 不能为空")
        for key in keywords:
            owner = keyword_owner.get(key)
            if owner and owner != agent_key:
                raise ValueError(
                    f"signal_router.rules 关键词重复冲突: {key} ({owner} vs {agent_key})"
                )
            keyword_owner[key] = agent_key


def route_signal_agent_key(*, signal_event: Dict[str, Any], router_config: Dict[str, Any] | None = None) -> str:
    """按事件类型/来源类别路由信号决策 agent（配置驱动）。"""
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
    cfg = dict(router_config or load_signal_router_config_from_env())
    rules = list(cfg.get("rules") or [])
    for item in rules:
        agent_key = str((item or {}).get("agent_key") or "").strip().lower()
        if not agent_key:
            continue
        keywords = [str(x).strip().lower() for x in list((item or {}).get("keywords") or []) if str(x).strip()]
        if any(k in text for k in keywords):
            return agent_key
    return str(cfg.get("default_agent_key") or "generic").strip().lower() or "generic"
