from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List


_DEFAULT_PROFILES = {
    "generic": {
        "focus": "generic_signal_validation",
        "checklist": ["direction_consistency", "evidence_quality", "market_regime_fit"],
        "avoid": ["position_sizing", "execution_action", "risk_gate_decision"],
    },
    "technical": {
        "focus": "technical_signal_validation",
        "checklist": ["trend_structure", "orderbook_liquidity", "oi_change_consistency"],
        "avoid": ["news_sentiment_overweight", "execution_action", "risk_gate_decision"],
    },
    "liquidation": {
        "focus": "liquidation_shock_validation",
        "checklist": ["liquidation_cluster_strength", "cascade_risk", "rebound_probability"],
        "avoid": ["long_horizon_macro_overweight", "execution_action", "risk_gate_decision"],
    },
    "onchain": {
        "focus": "onchain_flow_validation",
        "checklist": ["wallet_flow_direction", "exchange_inflow_outflow_shift", "source_reliability"],
        "avoid": ["micro_orderbook_overweight", "execution_action", "risk_gate_decision"],
    },
    "social_news": {
        "focus": "social_news_event_validation",
        "checklist": ["source_credibility", "cross_source_consistency", "timeliness_and_decay"],
        "avoid": ["single_post_overweight", "execution_action", "risk_gate_decision"],
    },
}


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "signal_decision_prompt_profiles.json"


def _normalize_prompt(item: Dict[str, Any], *, fallback: Dict[str, Any]) -> Dict[str, Any]:
    focus = str(item.get("focus") or fallback.get("focus") or "").strip() or str(fallback.get("focus") or "")
    checklist = [str(x).strip() for x in list(item.get("checklist") or fallback.get("checklist") or []) if str(x).strip()]
    avoid = [str(x).strip() for x in list(item.get("avoid") or fallback.get("avoid") or []) if str(x).strip()]
    model_id = str(item.get("model_id") or fallback.get("model_id") or "").strip()
    out = {"focus": focus, "checklist": checklist, "avoid": avoid}
    if model_id:
        out["model_id"] = model_id
    return out


@lru_cache(maxsize=8)
def _load_prompt_profiles(path: str) -> Dict[str, Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return dict(_DEFAULT_PROFILES)
    try:
        parsed = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return dict(_DEFAULT_PROFILES)
    if not isinstance(parsed, dict):
        return dict(_DEFAULT_PROFILES)
    out: Dict[str, Dict[str, Any]] = {}
    for key, fallback in _DEFAULT_PROFILES.items():
        node = parsed.get(key)
        if isinstance(node, dict):
            out[key] = _normalize_prompt(node, fallback=fallback)
        else:
            out[key] = dict(fallback)
    for raw_key, raw_node in parsed.items():
        key = str(raw_key or "").strip().lower()
        if not key or key in out:
            continue
        if isinstance(raw_node, dict):
            out[key] = _normalize_prompt(raw_node, fallback=_DEFAULT_PROFILES["generic"])
    return out


def reset_signal_decision_prompt_profiles_cache() -> None:
    _load_prompt_profiles.cache_clear()


def load_signal_decision_prompt_profiles_from_env() -> Dict[str, Dict[str, Any]]:
    raw = str(os.getenv("AGENT_SIGNAL_DECISION_PROMPT_CONFIG_FILE", "") or "").strip()
    path = raw if raw else str(_default_config_path())
    return _load_prompt_profiles(path)


def validate_signal_decision_prompt_profiles(
    cfg: Dict[str, Any],
    *,
    allowed_agent_keys: set[str] | None = None,
) -> None:
    if not isinstance(cfg, dict):
        raise ValueError("signal_decision_prompt_profiles 必须是对象")
    allowed = set([str(x).strip().lower() for x in list(allowed_agent_keys or set()) if str(x).strip()])
    if "generic" not in cfg:
        raise ValueError("signal_decision_prompt_profiles.generic 不能为空")
    for raw_key, raw_node in cfg.items():
        key = str(raw_key or "").strip().lower()
        if not key:
            raise ValueError("signal_decision_prompt_profiles 包含空键")
        if allowed and key not in allowed:
            raise ValueError(f"signal_decision_prompt_profiles 包含非法 agent_key: {key}")
        node = dict(raw_node or {}) if isinstance(raw_node, dict) else {}
        focus = str(node.get("focus") or "").strip()
        if not focus:
            raise ValueError(f"signal_decision_prompt_profiles.{key}.focus 不能为空")
        for field_name in ("checklist", "avoid"):
            arr = node.get(field_name)
            if arr is None:
                continue
            if not isinstance(arr, list):
                raise ValueError(f"signal_decision_prompt_profiles.{key}.{field_name} 必须是数组")
            for i, item in enumerate(list(arr)):
                if not str(item or "").strip():
                    raise ValueError(f"signal_decision_prompt_profiles.{key}.{field_name}[{i}] 不能为空")
        model_id = node.get("model_id")
        if model_id is not None and not str(model_id or "").strip():
            raise ValueError(f"signal_decision_prompt_profiles.{key}.model_id 不能为空字符串")
