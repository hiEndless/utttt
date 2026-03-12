from __future__ import annotations

from typing import Any, Dict, List


def safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def safe_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def safe_text(x: Any) -> str:
    try:
        return str(x or "")
    except Exception:
        return ""


def build_views(features: Any) -> Dict[str, Any]:
    mid = safe_dict(features.horizons.get("mid_term"))
    short = safe_dict(features.horizons.get("short_term"))
    mid_mb = safe_dict(mid.get("market_background"))
    short_mb = safe_dict(short.get("market_background"))
    mid_tm = safe_dict(mid_mb.get("trend_memory"))
    short_tm = safe_dict(short_mb.get("trend_memory"))

    return {
        "mid": mid,
        "short": short,
        "mid_mb": mid_mb,
        "short_mb": short_mb,
        "mid_tm": mid_tm,
        "short_tm": short_tm,
    }
