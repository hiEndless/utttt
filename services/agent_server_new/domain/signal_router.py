from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List


_SOURCE_CATEGORY_ALIASES = {
    "market_indicator": "technical",
    "market_indicator_signal": "technical",
    "technical_indicator": "technical",
    "indicator": "technical",
    "ta": "technical",
    "on_chain": "onchain",
    "onchain_wallet": "onchain",
    "wallet": "onchain",
    "chain": "onchain",
    "large_liquidation": "liquidation",
    "forced_liquidation": "liquidation",
    "social_media": "social",
    "social_news": "social",
    "headline_news": "news",
}


_DEFAULT_ROUTER_CONFIG = {
    "default_agent_key": "generic",
    "event_type_aliases": {
        "indicator_signal": "market_indicator_signal",
        "signal_indicator": "market_indicator_signal",
        "market_indicator_event": "market_indicator_signal",
        "technical_indicator_signal": "market_indicator_signal",
        "ta_signal": "market_indicator_signal",
        "msl_indicator_signal": "market_indicator_signal",
        "wallet_alert": "onchain_wallet_anomaly",
        "wallet_anomaly": "onchain_wallet_anomaly",
        "onchain_wallet_alert": "onchain_wallet_anomaly",
        "wallet_flow_anomaly": "onchain_wallet_anomaly",
        "whale_transfer_alert": "onchain_wallet_anomaly",
        "onchain_whale_alert": "onchain_wallet_anomaly",
        "forced_liquidation_cluster": "large_liquidation",
        "liquidation_cluster": "large_liquidation",
        "liquidation_spike": "large_liquidation",
        "liquidation_event": "large_liquidation",
        "forced_liquidation": "large_liquidation",
        "liquidation_whipsaw": "large_liquidation",
        "social_media_news": "social_news",
        "social_signal": "social_news",
        "news_event": "social_news",
        "social_news_signal": "social_news",
        "x_sentiment_alert": "social_news",
        "twitter_news": "social_news",
    },
    "event_type_routes": {
        "market_indicator_signal": "technical",
        "onchain_wallet_anomaly": "onchain",
        "large_liquidation": "liquidation",
        "macro_news": "social_news",
        "social_news": "social_news",
    },
    "source_category_routes": {
        "technical": "technical",
        "onchain": "onchain",
        "liquidation": "liquidation",
        "news": "social_news",
        "social": "social_news",
        "macro": "social_news",
    },
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
    raw_event_type_routes = parsed.get("event_type_routes")
    raw_event_type_aliases = parsed.get("event_type_aliases")
    raw_source_category_routes = parsed.get("source_category_routes")
    if not isinstance(rules, list):
        return {
            "default_agent_key": default_agent_key,
            "event_type_aliases": dict(_DEFAULT_ROUTER_CONFIG["event_type_aliases"]),
            "event_type_routes": dict(_DEFAULT_ROUTER_CONFIG["event_type_routes"]),
            "source_category_routes": dict(_DEFAULT_ROUTER_CONFIG["source_category_routes"]),
            "rules": list(_DEFAULT_ROUTER_CONFIG["rules"]),
        }
    event_type_routes: Dict[str, str] = {}
    if isinstance(raw_event_type_routes, dict):
        for k, v in raw_event_type_routes.items():
            key = str(k or "").strip().lower()
            value = str(v or "").strip().lower()
            if key and value:
                event_type_routes[key] = value
    if not event_type_routes:
        event_type_routes = {}
    event_type_aliases: Dict[str, str] = {}
    if isinstance(raw_event_type_aliases, dict):
        for k, v in raw_event_type_aliases.items():
            key = str(k or "").strip().lower()
            value = str(v or "").strip().lower()
            if key and value:
                event_type_aliases[key] = value
    if not event_type_aliases:
        event_type_aliases = dict(_DEFAULT_ROUTER_CONFIG["event_type_aliases"])
    source_category_routes: Dict[str, str] = {}
    if isinstance(raw_source_category_routes, dict):
        for k, v in raw_source_category_routes.items():
            key = str(k or "").strip().lower()
            value = str(v or "").strip().lower()
            if key and value:
                source_category_routes[key] = value
    if not source_category_routes:
        source_category_routes = {}
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
    return {
        "default_agent_key": default_agent_key,
        "event_type_aliases": event_type_aliases,
        "event_type_routes": event_type_routes,
        "source_category_routes": source_category_routes,
        "rules": normalized_rules,
    }


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
    """校验路由配置：未知 agent_key、映射字段格式、重复关键词冲突。"""
    if not isinstance(cfg, dict):
        raise ValueError("signal_router config 必须是对象")
    default_agent_key = str(cfg.get("default_agent_key") or "").strip().lower()
    if not default_agent_key:
        raise ValueError("signal_router.default_agent_key 不能为空")
    rules = cfg.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("signal_router.rules 必须是非空数组")
    event_type_routes = cfg.get("event_type_routes")
    if event_type_routes is not None and not isinstance(event_type_routes, dict):
        raise ValueError("signal_router.event_type_routes 必须是对象")
    event_type_aliases = cfg.get("event_type_aliases")
    if event_type_aliases is not None and not isinstance(event_type_aliases, dict):
        raise ValueError("signal_router.event_type_aliases 必须是对象")
    source_category_routes = cfg.get("source_category_routes")
    if source_category_routes is not None and not isinstance(source_category_routes, dict):
        raise ValueError("signal_router.source_category_routes 必须是对象")
    allowed = set([x.strip().lower() for x in list(allowed_agent_keys or set()) if str(x).strip()])
    if allowed and default_agent_key not in allowed:
        raise ValueError(f"signal_router.default_agent_key 非法: {default_agent_key}")
    for field_name, mapping in (
        ("event_type_aliases", event_type_aliases),
        ("event_type_routes", event_type_routes),
        ("source_category_routes", source_category_routes),
    ):
        if not isinstance(mapping, dict):
            continue
        for raw_key, raw_value in mapping.items():
            key = str(raw_key or "").strip().lower()
            value = str(raw_value or "").strip().lower()
            if not key:
                raise ValueError(f"signal_router.{field_name} 不能包含空键")
            if not value:
                raise ValueError(f"signal_router.{field_name}[{key}] 不能为空")
            if field_name == "event_type_aliases":
                continue
            if allowed and value not in allowed:
                raise ValueError(f"signal_router.{field_name}[{key}] 非法: {value}")
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
    """按事件类型/来源类别路由信号决策 agent（显式映射优先，关键词兜底）。"""
    payload = dict((signal_event or {}).get("payload") or {})
    cfg = dict(router_config or load_signal_router_config_from_env())
    event_type_aliases = dict(cfg.get("event_type_aliases") or {})
    event_type = str(
        payload.get("selected_type")
        or payload.get("selected_event_type")
        or payload.get("event_type")
        or payload.get("type")
        or payload.get("kind")
        or payload.get("signal_type")
        or ""
    ).strip().lower()
    if event_type:
        event_type = str(event_type_aliases.get(event_type) or event_type).strip().lower()
    source_category = str(
        payload.get("source_category")
        or payload.get("event_source_category")
        or payload.get("signal_source_type")
        or payload.get("source_type")
        or payload.get("source_signal_type")
        or ""
    ).strip().lower()
    source_obj = payload.get("source")
    source_name = ""
    if isinstance(source_obj, dict):
        source_name = str(source_obj.get("name") or "").strip().lower()
        if not source_category:
            source_category = str(source_obj.get("category") or "").strip().lower()
    elif source_obj:
        source_name = str(source_obj).strip().lower()
    source_category = str(_SOURCE_CATEGORY_ALIASES.get(source_category) or source_category).strip().lower()

    text = " ".join([event_type, source_category, source_name]).strip()
    event_type_routes = dict(cfg.get("event_type_routes") or {})
    source_category_routes = dict(cfg.get("source_category_routes") or {})
    event_route = str(event_type_routes.get(event_type) or "").strip().lower()
    if event_route:
        return event_route
    source_route = str(source_category_routes.get(source_category) or "").strip().lower()
    if source_route:
        return source_route
    rules = list(cfg.get("rules") or [])
    for item in rules:
        agent_key = str((item or {}).get("agent_key") or "").strip().lower()
        if not agent_key:
            continue
        keywords = [str(x).strip().lower() for x in list((item or {}).get("keywords") or []) if str(x).strip()]
        if any(k in text for k in keywords):
            return agent_key
    return str(cfg.get("default_agent_key") or "generic").strip().lower() or "generic"


def normalize_signal_event_type(
    *,
    signal_event: Dict[str, Any],
    router_config: Dict[str, Any] | None = None,
) -> Dict[str, str]:
    """归一化入口事件类型，供边界守卫与诊断使用。"""
    payload = dict((signal_event or {}).get("payload") or {})
    cfg = dict(router_config or load_signal_router_config_from_env())
    event_type_aliases = dict(cfg.get("event_type_aliases") or {})
    raw_event_type = str(
        payload.get("selected_type")
        or payload.get("selected_event_type")
        or payload.get("event_type")
        or payload.get("type")
        or payload.get("kind")
        or payload.get("signal_type")
        or ""
    ).strip().lower()
    normalized_event_type = str(event_type_aliases.get(raw_event_type) or raw_event_type).strip().lower()
    if not raw_event_type:
        matched = "empty"
    elif normalized_event_type != raw_event_type:
        matched = "alias"
    else:
        matched = "canonical_or_raw"
    return {
        "raw_event_type": raw_event_type,
        "normalized_event_type": normalized_event_type,
        "matched": matched,
    }
