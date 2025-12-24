# Agent Context Contract 定义（核心规范）

from typing import List, Literal, TypedDict


Scope = Literal["micro", "short", "mid", "long", "cross"]
Role = Literal[
    "liquidation_structure",
    "orderbook_microstructure",
    "technical_signal",
    "market_regime",
    "fusion_decision"
]


class AgentContextContract(TypedDict):
    agent: str

    # 该 Agent 被允许看到的字段路径（白名单）
    allowed_paths: List[str]

    # 该 Agent 的分析时间尺度边界
    scope: List[Scope]

    # 该 Agent 的分析职责
    role: Role

    # crowd_state 是否允许参与判断
    uses_crowd_state: bool

    # 是否允许跨周期外推（例如 short → mid）
    allows_cross_timeframe_inference: bool

    # 语义约束（仅用于校验与 Fusion 解释）
    forbidden_semantics: List[str]
