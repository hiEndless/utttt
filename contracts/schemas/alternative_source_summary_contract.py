from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Set, Tuple


_DEFAULT_SOURCES: Tuple[str, ...] = ("news", "social", "onchain")
_DEFAULT_REQUIRED_KEYS: Tuple[str, ...] = (
    "available_sources",
    "unavailable_sources",
    "provider_states",
    "data_sources",
    "inference_sources",
    "feature_keys",
    "evidence_counts",
)
_DEFAULT_PROVIDER_STATES: Set[str] = {
    "primary",
    "fallback",
    "static",
    "noop",
    "unavailable",
    "empty",
    "ok",
    "event_evidence_present",
}


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


@lru_cache(maxsize=1)
def _load_schema() -> Dict[str, Any]:
    path = Path(__file__).resolve().parent / "alternative_source_summary.schema.json"
    return _safe_dict(json.loads(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def get_alternative_source_required_keys() -> Tuple[str, ...]:
    required = tuple(str(x).strip() for x in list(_load_schema().get("required") or []) if str(x).strip())
    return required or _DEFAULT_REQUIRED_KEYS


@lru_cache(maxsize=1)
def get_alternative_source_names() -> Tuple[str, ...]:
    schema = _load_schema()
    available_items = _safe_dict(_safe_dict(schema.get("properties")).get("available_sources")).get("items")
    enums = [str(x).strip() for x in list(_safe_dict(available_items).get("enum") or []) if str(x).strip()]
    names = tuple(dict.fromkeys(enums))
    return names or _DEFAULT_SOURCES


@lru_cache(maxsize=1)
def get_alternative_source_provider_states_from_schema() -> Set[str]:
    schema = _load_schema()
    provider = _safe_dict(_safe_dict(schema.get("properties")).get("provider_states"))
    properties = _safe_dict(provider.get("properties"))
    values: Set[str] = set()
    for source in get_alternative_source_names():
        node = _safe_dict(properties.get(source))
        values.update({str(x).strip().lower() for x in list(node.get("enum") or []) if str(x).strip()})
    return values or set(_DEFAULT_PROVIDER_STATES)

