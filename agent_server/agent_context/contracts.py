# Agent Context Contract 定义（核心规范）

from typing import List, TypedDict


class _AgentContextContractRequired(TypedDict):
    agent: str


class AgentContextContract(_AgentContextContractRequired, total=False):
    # 该 Agent 明确禁止看到的字段路径（黑名单）
    forbidden_paths: List[str]
