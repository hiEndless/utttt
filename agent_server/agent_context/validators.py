# 合约校验（防越权）
# agent_context/validators.py
from .registry import AGENT_REGISTRY


def validate_agent(agent: str) -> None:
    if agent not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {agent}")


def forbid_full_context(agent: str) -> None:
    if agent != "fusion":
        raise ValueError(
            f"Agent '{agent}' is not allowed to request full context"
        )
