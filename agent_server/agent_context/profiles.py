# 字段裁剪 Profiles
# agent_context/profiles.py
from typing import List
from .registry import AGENT_REGISTRY


def get_forbidden_paths(agent: str) -> List[str]:
    key = agent.lower()
    contract = AGENT_REGISTRY.get(key)
    if not contract:
        return []
    return list(contract.get("forbidden_paths", []))
