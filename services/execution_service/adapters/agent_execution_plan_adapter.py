from __future__ import annotations

from typing import Any, Dict, Mapping

from contracts.schemas.alternative_source_summary_contract import (
    get_alternative_source_names,
    get_alternative_source_required_keys,
)

_ALT_SOURCES = get_alternative_source_names()
_ALT_SUMMARY_REQUIRED_KEYS = set(get_alternative_source_required_keys())


def _normalize_plan_direction(value: Any) -> str:
    direction = str(value or "").strip().lower()
    if direction not in {"long", "short", "neutral"}:
        raise ValueError("plan.direction 必须是 long/short/neutral")
    return direction


def _normalize_alternative_source_summary(value: Any) -> Dict[str, Any]:
    raw = value if isinstance(value, Mapping) else {}
    if not raw:
        return {}

    available = sorted(set([str(x) for x in list(raw.get("available_sources") or []) if str(x) in _ALT_SOURCES]))
    unavailable = sorted(set([str(x) for x in list(raw.get("unavailable_sources") or []) if str(x) in _ALT_SOURCES]))

    def _str_map(key: str, default: str = "") -> Dict[str, str]:
        src = raw.get(key)
        src_map = src if isinstance(src, Mapping) else {}
        out: Dict[str, str] = {}
        for name in _ALT_SOURCES:
            text = str(src_map.get(name) or default).strip()
            out[name] = text
        return out

    def _list_map(key: str) -> Dict[str, list[str]]:
        src = raw.get(key)
        src_map = src if isinstance(src, Mapping) else {}
        out: Dict[str, list[str]] = {}
        for name in _ALT_SOURCES:
            values = src_map.get(name)
            arr = values if isinstance(values, list) else []
            out[name] = sorted(set([str(x) for x in arr if str(x).strip()]))
        return out

    def _int_map(key: str) -> Dict[str, int]:
        src = raw.get(key)
        src_map = src if isinstance(src, Mapping) else {}
        out: Dict[str, int] = {}
        for name in _ALT_SOURCES:
            try:
                out[name] = max(0, int(src_map.get(name) or 0))
            except Exception:
                out[name] = 0
        return out

    out: Dict[str, Any] = {
        "available_sources": available,
        "unavailable_sources": unavailable,
        "provider_states": _str_map("provider_states"),
        "data_sources": _str_map("data_sources"),
        "inference_sources": _str_map("inference_sources"),
        "feature_keys": _list_map("feature_keys"),
        "evidence_counts": _int_map("evidence_counts"),
    }
    optional: Dict[str, Any] = {}
    preferred_source = str(raw.get("preferred_source") or "").strip()
    if preferred_source:
        optional["preferred_source"] = preferred_source
    conflict_count_raw = raw.get("conflict_count")
    try:
        if conflict_count_raw is not None:
            optional["conflict_count"] = max(0, int(conflict_count_raw))
    except Exception:
        optional["conflict_count"] = 0
    out.update(optional)
    if not _ALT_SUMMARY_REQUIRED_KEYS.issubset(set(out.keys())):
        return {}
    return out


def adapt_agent_execution_plan_to_decision_intent(
    *,
    decision_id: str,
    exchange: str,
    symbol: str,
    plan: Mapping[str, Any],
    cross_horizon_policy: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """把 agent 输出的最小 ExecutionPlan 语义映射到 DecisionIntent v1。"""

    direction = _normalize_plan_direction(plan.get("direction", "neutral"))
    decision_conf_raw = plan.get("decision_confidence")
    legacy_conf_raw = plan.get("confidence")
    confidence = decision_conf_raw or legacy_conf_raw or {"level": "low", "score": 0.0}
    if not isinstance(confidence, dict):
        confidence = {"level": "low", "score": 0.0}
    confidence_source = (
        "decision_confidence"
        if isinstance(decision_conf_raw, dict)
        else ("confidence_legacy" if isinstance(legacy_conf_raw, dict) else "default")
    )

    # execution_action 语义用于保留 agent 的动作建议，不作为硬裁决依据。
    agent_action = str(plan.get("action", "hold")).strip().lower()
    risk_hints: Dict[str, Any] = {
        "agent_action_hint": agent_action,
        "decision_confidence": dict(confidence),
        "decision_confidence_source": confidence_source,
    }
    notes = str(plan.get("notes", "")).strip()
    if notes:
        risk_hints["agent_notes"] = notes
    alt_summary = _normalize_alternative_source_summary(plan.get("alternative_source_summary"))
    if alt_summary:
        risk_hints["alternative_source_summary"] = alt_summary

    out = {
        "decision_id": decision_id,
        "exchange": exchange,
        "symbol": symbol,
        "direction_intent": direction,
        "decision_confidence": dict(confidence),
        "cross_horizon_policy": dict(cross_horizon_policy or {}),
        "risk_hints": risk_hints,
    }
    # 中文注释：agent->execution 默认只发送 canonical 字段 decision_confidence，避免新流量继续扩散 deprecated 别名。
    return out
