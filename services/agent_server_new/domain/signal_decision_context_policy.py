from __future__ import annotations

from typing import Any, Dict, Iterable, List


_ALLOWED_AGENT_KEYS = {"technical", "liquidation", "onchain", "social_news", "generic"}

_AGENT_EVENT_KEYWORDS = {
    "technical": {"technical", "indicator", "orderbook", "funding", "basis", "signal", "strategy"},
    "liquidation": {"liquidation", "liq", "squeeze", "forced_liq", "forced_liquidation"},
    "onchain": {"onchain", "wallet", "whale", "exchange_flow", "nansen", "glassnode", "arkham", "chain"},
    "social_news": {"social", "news", "macro", "sentiment", "twitter", "reddit", "reuters", "bloomberg"},
    "generic": set(),
}

_AGENT_FEATURE_KEYWORDS = {
    "technical": {"cross_horizon", "anomaly_flags", "liquidity", "orderbook", "oi_", "trend", "volatility", "memory"},
    "liquidation": {"cross_horizon", "liquidation", "anomaly_flags", "liquidity", "oi_", "risk", "memory"},
    "onchain": {"cross_horizon", "alternative_source_summary", "onchain", "wallet", "whale", "flow", "memory"},
    "social_news": {"cross_horizon", "alternative_source_summary", "social", "news", "macro", "sentiment", "memory"},
    "generic": {"cross_horizon", "alternative_source_summary", "anomaly_flags", "memory"},
}


def normalize_decision_agent_key(value: Any) -> str:
    key = str(value or "").strip().lower()
    return key if key in _ALLOWED_AGENT_KEYS else "generic"


def _score_of_event(event: Dict[str, Any]) -> float:
    try:
        return float((event or {}).get("score") or 0.0)
    except Exception:
        return 0.0


def _event_text(event: Dict[str, Any]) -> str:
    evt = dict(event or {})
    evidence = dict(evt.get("evidence") or {})
    tokens = [
        str(evt.get("type") or ""),
        str(evt.get("source") or ""),
        str(evt.get("event_source_category") or ""),
        str(evidence.get("event_source_category") or ""),
        str(evidence.get("event_source") or ""),
    ]
    return " ".join([x.strip().lower() for x in tokens if str(x).strip()])


def _feature_name(item: Dict[str, Any]) -> str:
    return str((item or {}).get("name") or "").strip().lower()


def _contains_any(text: str, patterns: Iterable[str]) -> bool:
    if not text:
        return False
    return any(str(p or "").strip().lower() in text for p in list(patterns or []))


def clip_active_events_for_agent(
    *,
    decision_agent_key: str,
    active_events: List[Dict[str, Any]],
    max_items: int = 8,
) -> List[Dict[str, Any]]:
    key = normalize_decision_agent_key(decision_agent_key)
    limit = max(1, int(max_items))
    items = [dict(x or {}) for x in list(active_events or []) if isinstance(x, dict)]
    if not items:
        return []
    keywords = set(_AGENT_EVENT_KEYWORDS.get(key) or set())
    scored = sorted(items, key=_score_of_event, reverse=True)
    if not keywords:
        return scored[:limit]
    matched = [evt for evt in scored if _contains_any(_event_text(evt), keywords)]
    if len(matched) >= limit:
        return matched[:limit]
    used_ids = {id(x) for x in matched}
    extra = [evt for evt in scored if id(evt) not in used_ids]
    return [*matched, *extra][:limit]


def clip_key_market_features_for_agent(
    *,
    decision_agent_key: str,
    key_market_features: Dict[str, Any],
    max_items: int = 8,
) -> Dict[str, Any]:
    key = normalize_decision_agent_key(decision_agent_key)
    limit = max(1, int(max_items))
    src = dict(key_market_features or {})
    features = [dict(x or {}) for x in list(src.get("features") or []) if isinstance(x, dict)]
    keywords = set(_AGENT_FEATURE_KEYWORDS.get(key) or set())
    selected: List[Dict[str, Any]] = []
    for item in features:
        name = _feature_name(item)
        if _contains_any(name, keywords):
            selected.append(item)
        if len(selected) >= limit:
            break
    if not selected:
        selected = features[:limit]
    return {
        "profile": str(src.get("profile") or ""),
        "features": selected[:limit],
        "contract_warnings": list(src.get("contract_warnings") or []),
    }


def build_llm_observation_context(
    *,
    decision_agent_key: str,
    key_market_features: Dict[str, Any],
    active_events: List[Dict[str, Any]],
    features_limit: int = 8,
    events_limit: int = 8,
) -> Dict[str, Any]:
    key = normalize_decision_agent_key(decision_agent_key)
    return {
        "decision_agent_key": key,
        "key_market_features": clip_key_market_features_for_agent(
            decision_agent_key=key,
            key_market_features=key_market_features,
            max_items=features_limit,
        ),
        "active_events": clip_active_events_for_agent(
            decision_agent_key=key,
            active_events=active_events,
            max_items=events_limit,
        ),
    }
