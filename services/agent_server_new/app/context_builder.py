from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from services.agent_server_new.app.workflows.event_context import EventContext
from services.agent_server_new.ports.data.active_events_provider import ActiveEventsProvider
from services.agent_server_new.ports.memory.symbol_memory_provider import SymbolMemoryProvider
from services.agent_server_new.ports.data.position_context_provider import PositionContextProvider
from services.agent_server_new.ports.market_state import MarketStateProvider


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_risk_flags(value: Any) -> List[str]:
    if isinstance(value, list):
        return sorted(set([str(x) for x in value if str(x or "").strip()]))
    if isinstance(value, dict):
        out: List[str] = []
        for k, v in value.items():
            name = str(k or "").strip()
            if not name:
                continue
            if isinstance(v, str) and v.strip().lower() in {"0", "false", "no", "off", ""}:
                continue
            if bool(v):
                out.append(name)
        return sorted(set(out))
    return []


def _extract_contract_warnings(anomaly_flags: List[Any]) -> List[str]:
    out: List[str] = []
    for item in list(anomaly_flags or []):
        flag = str(item or "").strip()
        if not flag:
            continue
        if flag.startswith("state_features_") or flag.startswith("msl_"):
            out.append(flag)
    return sorted(set(out))


def _extract_alternative_source_summary(evidence: Dict[str, Any]) -> Dict[str, Any]:
    alt = _safe_dict(evidence.get("alternative_sources"))
    sources = ("news", "social", "onchain")
    provider_states: Dict[str, str] = {}
    available_sources: List[str] = []
    unavailable_sources: List[str] = []
    feature_keys: Dict[str, List[str]] = {}

    for name in sources:
        node = _safe_dict(alt.get(name))
        state = str(node.get("provider_state") or "empty")
        provider_states[name] = state
        available = bool(node.get("available") is True)
        if available:
            available_sources.append(name)
        else:
            unavailable_sources.append(name)
        feature_keys[name] = sorted([str(k) for k in _safe_dict(node.get("features")).keys() if str(k).strip()])

    return {
        "available_sources": available_sources,
        "unavailable_sources": unavailable_sources,
        "provider_states": provider_states,
        "feature_keys": feature_keys,
    }


def _normalize_recent_memory(
    *,
    recent: List[Dict[str, Any]],
    now_ms: int,
    ttl_ms: int,
    topk: int,
    dedup_key: str,
) -> List[Dict[str, Any]]:
    clean = [dict(item) for item in list(recent or []) if isinstance(item, dict)]

    if ttl_ms > 0:
        cutoff = now_ms - int(ttl_ms)
        clean = [item for item in clean if _to_int(item.get("ts"), 0) >= cutoff]

    dedup_key_norm = str(dedup_key or "").strip()
    if dedup_key_norm:
        seen = set()
        deduped_reversed: List[Dict[str, Any]] = []
        # 从新到旧做去重，保留最新条目，再恢复时间升序。
        for item in reversed(clean):
            key = str(item.get(dedup_key_norm) or "").strip()
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            deduped_reversed.append(item)
        clean = list(reversed(deduped_reversed))

    if topk > 0 and len(clean) > topk:
        clean = clean[-topk:]
    return clean


def _build_memory_observability(
    *,
    raw_recent: List[Dict[str, Any]],
    filtered_recent: List[Dict[str, Any]],
    memory_summary: Dict[str, Any],
) -> Dict[str, Any]:
    raw_count = len(list(raw_recent or []))
    filtered_count = len(list(filtered_recent or []))
    summary_fields = len(dict(memory_summary or {}).keys())
    summary_event_count = _to_int(dict(memory_summary or {}).get("event_count"), 0)
    dropped_total = max(0, raw_count - filtered_count)
    return {
        "memory_hit": bool(summary_fields > 0 or filtered_count > 0),
        "memory_raw_recent_count": raw_count,
        "memory_filtered_recent_count": filtered_count,
        "memory_dropped_count": dropped_total,
        "memory_summary_field_count": summary_fields,
        "memory_summary_event_count": summary_event_count,
    }


def _signal_context_builder(
    *,
    features: Dict[str, Any],
    signal_event: Dict[str, Any],
    active_events: List[Dict[str, Any]],
    max_features: int = 10,
    cross_horizon: Dict[str, Any] | None = None,
    msl_meta: Dict[str, Any] | None = None,
    symbol_memory: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """按信号类型动态选择证据：避免把所有证据一股脑塞给 LLM。"""

    f = _safe_dict(features)
    evidence = _safe_dict(f.get("evidence"))
    anomalies = _safe_dict(f.get("anomalies"))
    orderbook = _safe_dict(f.get("orderbook"))
    open_interest = _safe_dict(f.get("open_interest"))
    horizons = _safe_dict(f.get("horizons"))
    alternative_source_summary = _extract_alternative_source_summary(evidence)

    payload = _safe_dict(_safe_dict(signal_event).get("payload"))
    event_type = str(payload.get("event_type") or payload.get("type") or payload.get("kind") or "").lower()
    profile = "generic"
    if any(k in event_type for k in ("liquidation", "liq", "squeeze")):
        profile = "liquidation"
    elif any(k in event_type for k in ("news", "social", "macro", "onchain")):
        profile = "macro_sentiment"
    elif any(k in event_type for k in ("indicator", "signal", "strategy")):
        profile = "indicator_signal"

    candidates: List[Tuple[str, Any]]
    if profile == "liquidation":
        candidates = [
            ("anomaly_flags", _safe_dict(anomalies).get("flags")),
            ("liquidation_cluster_flag", "liquidation_cluster" in set(_safe_dict(anomalies).get("flags") or [])),
            ("liquidity_vacuum", _safe_dict(orderbook).get("liquidity_vacuum")),
            ("orderbook_stability", _safe_dict(orderbook).get("stability")),
            ("delta_oi_pct", _safe_dict(open_interest).get("delta_oi_pct")),
            ("oi_risk_flags", _normalize_risk_flags(_safe_dict(open_interest).get("risk_flags"))),
            ("mid_trend_memory", _safe_dict(_safe_dict(horizons).get("mid_term")).get("market_background", {}).get("trend_memory")),
        ]
    elif profile == "macro_sentiment":
        candidates = [
            ("alternative_source_summary", alternative_source_summary),
            ("anomaly_flags", _safe_dict(anomalies).get("flags")),
            ("oi_trend", _safe_dict(open_interest).get("oi_trend")),
            ("oi_velocity", _safe_dict(open_interest).get("oi_velocity")),
            ("mid_trend_context", _safe_dict(_safe_dict(horizons).get("mid_term")).get("market_background", {}).get("trend_context")),
            ("mid_participants", _safe_dict(_safe_dict(horizons).get("mid_term")).get("participant_background")),
            ("active_events_top", list(active_events or [])[:5]),
        ]
    else:
        candidates = [
            ("alternative_source_summary", alternative_source_summary),
            ("anomaly_flags", _safe_dict(anomalies).get("flags")),
            ("liquidity_vacuum", _safe_dict(orderbook).get("liquidity_vacuum")),
            ("orderbook_stability", _safe_dict(orderbook).get("stability")),
            ("delta_oi_pct", _safe_dict(open_interest).get("delta_oi_pct")),
            ("oi_trend", _safe_dict(open_interest).get("oi_trend")),
            ("oi_velocity", _safe_dict(open_interest).get("oi_velocity")),
            ("oi_acceleration", _safe_dict(open_interest).get("oi_acceleration")),
            ("oi_risk_flags", _normalize_risk_flags(_safe_dict(open_interest).get("risk_flags"))),
            ("mid_trend_memory", _safe_dict(_safe_dict(horizons).get("mid_term")).get("market_background", {}).get("trend_memory")),
            ("mid_trend_context", _safe_dict(_safe_dict(horizons).get("mid_term")).get("market_background", {}).get("trend_context")),
        ]

    out: List[Dict[str, Any]] = []
    # 固定注入跨周期摘要，保证下游可直接消费 suggested_policy。
    if isinstance(cross_horizon, dict) and cross_horizon:
        out.append({"name": "cross_horizon", "value": dict(cross_horizon)})
    if isinstance(msl_meta, dict) and msl_meta:
        out.append({"name": "msl_meta", "value": dict(msl_meta)})
    memory_summary = _safe_dict(_safe_dict(symbol_memory).get("summary"))
    recent_memory = list(_safe_dict(symbol_memory).get("recent") or [])
    if memory_summary:
        out.append({"name": "memory_summary", "value": memory_summary})
    if recent_memory:
        out.append({"name": "recent_memory", "value": recent_memory})

    for name, value in candidates:
        if value is None:
            continue
        out.append({"name": name, "value": value})
        if len(out) >= int(max_features):
            break

    return {"profile": profile, "features": out, "evidence": evidence, "anomalies": anomalies}


@dataclass(frozen=True)
class BuiltContext:
    """ContextBuilder 的输出：包含 EventContext 与 raw_market_structure（便于审计）。"""

    ctx: EventContext
    raw_market_structure: Dict[str, Any]


class ContextBuilder:
    """组装上下文：market_state + position_context + signal_event。"""

    def __init__(
        self,
        *,
        market_state: MarketStateProvider,
        position_context: PositionContextProvider,
        active_events: ActiveEventsProvider,
        symbol_memory_provider: SymbolMemoryProvider | None = None,
        max_key_features: int = 10,
        memory_recent_topk: int = 5,
        memory_recent_ttl_ms: int = 24 * 60 * 60 * 1000,
        memory_dedup_key: str = "event_id",
    ) -> None:
        self._market_state = market_state
        self._position_context = position_context
        self._active_events = active_events
        self._symbol_memory_provider = symbol_memory_provider
        self._max_key_features = int(max_key_features)
        self._memory_recent_topk = max(1, int(memory_recent_topk))
        self._memory_recent_ttl_ms = max(0, int(memory_recent_ttl_ms))
        self._memory_dedup_key = str(memory_dedup_key or "event_id").strip() or "event_id"

    async def build(
        self,
        *,
        event_id: str,
        exchange: str,
        symbol: str,
        signal_payload: Dict[str, Any],
    ) -> BuiltContext:
        market_state = await self._market_state.get_market_state(exchange, symbol)
        position_ctx = await self._position_context.get_position_context(exchange, symbol)
        active_events = await self._active_events.get_active_events(exchange, symbol)
        symbol_memory = (
            await self._symbol_memory_provider.get_symbol_memory(exchange, symbol, limit=5)
            if self._symbol_memory_provider is not None
            else {}
        )
        memory_summary = _safe_dict(_safe_dict(symbol_memory).get("summary"))
        memory_recent = _normalize_recent_memory(
            recent=list(_safe_dict(symbol_memory).get("recent") or []),
            now_ms=int(time.time() * 1000),
            ttl_ms=self._memory_recent_ttl_ms,
            topk=self._memory_recent_topk,
            dedup_key=self._memory_dedup_key,
        )
        memory_observability = _build_memory_observability(
            raw_recent=list(_safe_dict(symbol_memory).get("recent") or []),
            filtered_recent=memory_recent,
            memory_summary=memory_summary,
        )
        symbol_memory_filtered = {"summary": memory_summary, "recent": memory_recent}

        signal_event = {"event_id": event_id, "exchange": exchange, "symbol": symbol, "payload": dict(signal_payload)}
        key_features = _signal_context_builder(
            features=dict(market_state.state_features or {}),
            signal_event=signal_event,
            active_events=list(active_events),
            max_features=self._max_key_features,
            cross_horizon=dict(market_state.cross_horizon or {}),
            msl_meta=dict(market_state.msl_meta or {}),
            symbol_memory=symbol_memory_filtered,
        )
        key_features["memory_observability"] = memory_observability
        key_features["contract_warnings"] = _extract_contract_warnings(list(market_state.anomaly_flags or []))
        ctx = EventContext(
            event_id=event_id,
            exchange=exchange,
            symbol=symbol,
            timestamp_ms=EventContext.now_ms(),
            signal_event=signal_event,
            msl=market_state.msl,
            key_market_features=key_features,
            active_events=list(active_events),
            position_context=position_ctx,
        )
        return BuiltContext(ctx=ctx, raw_market_structure=dict(market_state.raw_market_structure or {}))
