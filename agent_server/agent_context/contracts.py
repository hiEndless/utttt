# Agent Context Contract 定义（核心规范）

from typing import List, Literal, TypedDict


Scope = Literal["micro", "short", "mid", "long", "cross"]
Role = Literal[
    "liquidation_structure",
    "orderbook_microstructure",
    "technical_signal",
    "market_regime",
    "fusion_decision",
    "risk_management",
    "trade_analysis",
]


class _AgentContextContractRequired(TypedDict):
    agent: str

    # 该 Agent 的分析时间尺度边界
    scope: List[Scope]

    # 该 Agent 的分析职责
    role: Role

    # crowd_state 是否允许参与判断
    uses_crowd_state: bool

    # 是否允许跨周期外推（例如 short → mid）
    allows_cross_timeframe_inference: bool


class AgentContextContract(_AgentContextContractRequired, total=False):
    # 该 Agent 明确禁止看到的字段路径（黑名单）
    forbidden_paths: List[str]
