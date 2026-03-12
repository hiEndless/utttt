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
