from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


Direction = Literal["long", "short", "none"]
RiskAction = Literal["add", "reduce", "hold", "exit", "skip"]
ActionIntentType = Literal["increase", "decrease", "close", "hold", "skip"]


@dataclass(frozen=True)
class Confidence:
    """置信度：用于让上层在不确定时倾向于保守或降级。"""

    level: Literal["high", "medium", "low"]
    score: float


@dataclass(frozen=True)
class SignalVerdict:
    """信号有效性裁决：只描述“信号是否成立”，不直接给仓位动作。"""

    direction: Direction
    verdict: Literal["accept", "reject", "uncertain"]
    confidence: Confidence
    invalidation_reasons: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class SignalDecision:
    """信号语义裁决：仅表达信号可信度，不表达执行动作。"""

    decision_id: str
    exchange: str
    symbol: str
    decision_agent_key: str
    signal_direction: Direction
    signal_verdict: Literal["accept", "reject", "uncertain"]
    confidence: Confidence
    reliability_score: float
    reasons: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    llm_observation: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionIntent:
    """动作意图：用于把“策略动作语义”与“执行细节/约束”解耦。"""

    intent: ActionIntentType
    direction: Direction
    confidence: Confidence
    reasons: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class RulePlan:
    """规则规划输出：在 intent 之上补齐 sizing 等可执行前的规则化计划。"""

    intent: ActionIntent
    sizing: Dict[str, Any] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class RiskAllowance:
    """风控许可：用于把“动作”与“是否允许”拆开。"""

    allow_open: bool
    allow_add: bool
    allow_reduce: bool
    allow_exit: bool
    reasons: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionPlan:
    """最终执行计划：可直接落库/推送执行器。"""

    action: RiskAction
    direction: Direction
    allowance: RiskAllowance
    confidence: Confidence
    sizing: Optional[Dict[str, Any]] = None
    notes: str = ""
