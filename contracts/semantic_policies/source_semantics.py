from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Set

import yaml

_DEFAULT_ALLOWED_PROVIDER_STATES: Set[str] = {
    "primary",
    "fallback",
    "static",
    "noop",
    "unavailable",
    "empty",
    "ok",
    "event_evidence_present",
}
_DEFAULT_UNAVAILABLE_PROVIDER_STATES: Set[str] = {"noop", "empty", "unavailable", "none"}


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _render_source_template(template: str, *, source: str, fallback: str) -> str:
    text = str(template or "").strip()
    if not text:
        return fallback
    try:
        rendered = text.format(source=source)
    except Exception:
        return fallback
    return str(rendered or "").strip() or fallback


@lru_cache(maxsize=1)
def _load_policy() -> Dict[str, Any]:
    path = Path(__file__).resolve().parent / "source_semantics.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    policies = list(_safe_dict(data).get("policies") or [])
    for item in policies:
        row = _safe_dict(item)
        if str(row.get("name") or "") == "alternative_sources_summary":
            return row
    return {}


def get_alternative_source_allowed_provider_states() -> Set[str]:
    item = _load_policy()
    provider_policy = _safe_dict(item.get("provider_state_policy"))
    enums = _safe_dict(provider_policy.get("enums"))
    allowed: Set[str] = set()
    for scope in ("feature", "event_center", "market_state_fusion"):
        allowed.update([str(x).strip().lower() for x in list(enums.get(scope) or []) if str(x).strip()])
    return allowed or set(_DEFAULT_ALLOWED_PROVIDER_STATES)


def get_alternative_source_unavailable_provider_states() -> Set[str]:
    item = _load_policy()
    provider_policy = _safe_dict(item.get("provider_state_policy"))
    unavailable = {str(x).strip().lower() for x in list(provider_policy.get("unavailable_states") or []) if str(x).strip()}
    return unavailable or set(_DEFAULT_UNAVAILABLE_PROVIDER_STATES)


def _get_default_rules() -> Dict[str, Any]:
    item = _load_policy()
    return _safe_dict(item.get("default_rules"))


def _get_rule(rule_name: str) -> Dict[str, Any]:
    return _safe_dict(_get_default_rules().get(rule_name))


def get_event_center_present_provider_state() -> str:
    item = _load_policy()
    provider_policy = _safe_dict(item.get("provider_state_policy"))
    enums = _safe_dict(provider_policy.get("enums"))
    event_center_values = [str(x).strip().lower() for x in list(enums.get("event_center") or []) if str(x).strip()]
    if "event_evidence_present" in event_center_values:
        return "event_evidence_present"
    unavailable = get_alternative_source_unavailable_provider_states()
    for value in event_center_values:
        if value not in unavailable and value != "empty":
            return value
    return "event_evidence_present"


def get_event_center_empty_provider_state() -> str:
    item = _load_policy()
    provider_policy = _safe_dict(item.get("provider_state_policy"))
    enums = _safe_dict(provider_policy.get("enums"))
    event_center_values = [str(x).strip().lower() for x in list(enums.get("event_center") or []) if str(x).strip()]
    if "empty" in event_center_values:
        return "empty"
    unavailable = get_alternative_source_unavailable_provider_states()
    for value in event_center_values:
        if value in unavailable:
            return value
    return "empty"


def get_event_center_data_source(source: str) -> str:
    fallback = f"event_center_new.{source}"
    event_center = _get_rule("event_center")
    template = str(event_center.get("data_source_template") or "")
    return _render_source_template(template, source=source, fallback=fallback)


def get_event_center_inference_source() -> str:
    event_center = _get_rule("event_center")
    value = str(event_center.get("inference_source") or "").strip()
    return value or "event_center_new.selector"


def get_market_state_feature_fallback_data_source(source: str) -> str:
    fallback = f"feature_service.{source}"
    rule = _get_rule("market_state_feature_fallback")
    template = str(rule.get("data_source_template") or "")
    return _render_source_template(template, source=source, fallback=fallback)


def get_market_state_feature_fallback_inference_source() -> str:
    rule = _get_rule("market_state_feature_fallback")
    value = str(rule.get("inference_source") or "").strip()
    return value or "feature_service.normalizer"


def get_market_state_event_fallback_data_source(source: str) -> str:
    fallback = f"event_center_new.{source}"
    rule = _get_rule("market_state_event_fallback")
    template = str(rule.get("data_source_template") or "")
    return _render_source_template(template, source=source, fallback=fallback)


def get_market_state_event_fallback_inference_source() -> str:
    rule = _get_rule("market_state_event_fallback")
    value = str(rule.get("inference_source") or "").strip()
    return value or "event_center_new.selector"


def get_agent_fusion_feature_data_source(source: str) -> str:
    fallback = f"feature_service.{source}"
    rule = _get_rule("agent_fusion_fallback")
    template = str(rule.get("feature_data_source_template") or "")
    return _render_source_template(template, source=source, fallback=fallback)


def get_agent_fusion_event_data_source(source: str) -> str:
    fallback = f"event_center_new.{source}"
    rule = _get_rule("agent_fusion_fallback")
    template = str(rule.get("event_data_source_template") or "")
    return _render_source_template(template, source=source, fallback=fallback)


def get_agent_fusion_feature_inference_source() -> str:
    rule = _get_rule("agent_fusion_fallback")
    value = str(rule.get("feature_inference_source") or "").strip()
    return value or "feature_service.normalizer"


def get_agent_fusion_event_inference_source() -> str:
    rule = _get_rule("agent_fusion_fallback")
    value = str(rule.get("event_inference_source") or "").strip()
    return value or "event_center_new.selector"
