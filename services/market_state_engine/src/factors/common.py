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
