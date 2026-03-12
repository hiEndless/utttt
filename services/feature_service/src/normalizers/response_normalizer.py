from __future__ import annotations

from typing import Any, Dict, List

from contracts.semantic_policies.source_semantics import (
    get_alternative_source_allowed_provider_states,
    get_alternative_source_unavailable_provider_states,
)

VALID_HORIZONS = ("short_term", "mid_term", "long_term")
_ALTERNATIVE_SOURCE_ALLOWED_PROVIDER_STATES = get_alternative_source_allowed_provider_states()
_UNAVAILABLE_PROVIDER_STATES = get_alternative_source_unavailable_provider_states()


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _normalize_horizons(values: Any) -> List[str]:
    # 统一候选周期，保证字段稳定且顺序可预测。
    src = values if isinstance(values, list) else []
    out: List[str] = []
    for h in src:
        hs = str(h or "").strip()
        if hs in VALID_HORIZONS and hs not in out:
            out.append(hs)
    return out or list(VALID_HORIZONS)


def normalize_exchange(exchange: Any) -> str:
    return str(exchange or "").strip().lower()


def normalize_symbol(symbol: Any) -> str:
    return str(symbol or "").strip().upper()


def normalize_degraded_reasons(reasons: Any) -> List[str]:
    src = reasons if isinstance(reasons, list) else []
    out: List[str] = []
    for r in src:
        rs = str(r or "").strip()
        if rs and rs not in out:
            out.append(rs)
    return out


def normalize_raw_market_structure(raw_market_structure: Any, *, symbol: str) -> Dict[str, Any]:
    raw = _safe_dict(raw_market_structure)
    return {
        "symbol": normalize_symbol(raw.get("symbol") or symbol),
        "candidate_horizons": _normalize_horizons(raw.get("candidate_horizons")),
        "pre_decision_structure": _safe_dict(raw.get("pre_decision_structure")),
        "horizons": _safe_dict(raw.get("horizons")),
        "orderbook": _safe_dict(raw.get("orderbook")),
        "open_interest": _safe_dict(raw.get("open_interest")),
        "behavioral": _safe_dict(raw.get("behavioral")),
    }


def normalize_features_payload(features: Any) -> Dict[str, Any]:
    def _normalize_alt_entry(source_type: str, payload: Any) -> Dict[str, Any]:
        raw = _safe_dict(payload)
        features = _safe_dict(raw.get("features"))
        available = bool(raw.get("available")) if "available" in raw else bool(features)
        provider_state = str(raw.get("provider_state") or ("ok" if available else "empty")).strip().lower()
        if provider_state in _UNAVAILABLE_PROVIDER_STATES and not features:
            available = False
        if provider_state not in _ALTERNATIVE_SOURCE_ALLOWED_PROVIDER_STATES:
            provider_state = "ok" if (available or bool(features)) else "empty"
        return {
            "source_type": source_type,
            "available": available,
            "provider_state": provider_state,
            "as_of_ms": raw.get("as_of_ms"),
            "features": features,
        }

    src = _safe_dict(features)
    derived_metrics = _safe_dict(src.get("derived_metrics"))
    alt = _safe_dict(src.get("alternative_sources"))
    return {
        "indicators": _safe_dict(src.get("indicators")),
        "derived_metrics": {
            **derived_metrics,
            "candidate_horizons": _normalize_horizons(derived_metrics.get("candidate_horizons")),
            "indicator_metrics": _safe_dict(derived_metrics.get("indicator_metrics")),
            "horizon_metrics": _safe_dict(derived_metrics.get("horizon_metrics")),
            "orderbook_metrics": _safe_dict(derived_metrics.get("orderbook_metrics")),
            "open_interest_metrics": _safe_dict(derived_metrics.get("open_interest_metrics")),
            "behavior_metrics": _safe_dict(derived_metrics.get("behavior_metrics")),
            "pre_decision_metrics": _safe_dict(derived_metrics.get("pre_decision_metrics")),
        },
        "structure_snapshot": {
            "pre_decision_structure": _safe_dict(_safe_dict(src.get("structure_snapshot")).get("pre_decision_structure")),
            "horizons": _safe_dict(_safe_dict(src.get("structure_snapshot")).get("horizons")),
        },
        "alternative_sources": {
            "news": _normalize_alt_entry("news", alt.get("news")),
            "social": _normalize_alt_entry("social", alt.get("social")),
            "onchain": _normalize_alt_entry("onchain", alt.get("onchain")),
        },
    }
