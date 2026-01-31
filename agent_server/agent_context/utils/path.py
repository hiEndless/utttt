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


def delete_by_path(out: Dict[str, Any], path: str) -> None:
    """按路径删除字段；不存在则忽略，并向上清理空 dict。"""
    parts = path.split(".")
    if not parts:
        return

    cur: Any = out
    stack: list[tuple[Dict[str, Any], str]] = []
    for p in parts[:-1]:
        if not isinstance(cur, dict) or p not in cur:
            return
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            return
        stack.append((cur, p))
        cur = nxt

    if not isinstance(cur, dict):
        return
    cur.pop(parts[-1], None)

    while stack:
        parent, key = stack.pop()
        child = parent.get(key)
        if isinstance(child, dict) and not child:
            parent.pop(key, None)
        else:
            break
