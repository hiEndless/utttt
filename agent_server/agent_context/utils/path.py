# 通用工具（path get/set, deep copy 等）
# agent_context/utils.py
from typing import Any, Dict


def get_by_path(obj: Dict[str, Any], path: str) -> Any:
    cur: Any = obj
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def set_by_path(out: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur = out
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value
