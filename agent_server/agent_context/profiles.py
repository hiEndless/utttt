# 字段白名单 Profiles
# agent_context/profiles.py
from typing import Dict, List
from .registry import AGENT_REGISTRY


def get_allowed_paths(agent: str) -> List[str]:
    key = agent.lower()
    contract = AGENT_REGISTRY.get(key)
    if not contract:
        return []
    return list(contract.get("allowed_paths", []))
