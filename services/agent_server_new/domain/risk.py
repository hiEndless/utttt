from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional

from .contracts import Confidence, ExecutionPlan, RiskAllowance, SignalVerdict


@dataclass(frozen=True)
class RiskContext:
    """风控上下文：只放硬约束需要的字段，避免引入大上下文耦合。"""

    global_regime: Literal["normal", "elevated", "critical"]
    cooldown_active: bool


def gate_allowance(ctx: RiskContext) -> RiskAllowance:
    """硬门控：决定哪些动作在系统层面允许。"""

    if ctx.global_regime == "critical":
        return RiskAllowance(
            allow_open=False,
            allow_add=False,
            allow_reduce=True,
            allow_exit=True,
            reasons=["global_regime_critical"],
        )
    if ctx.cooldown_active:
        return RiskAllowance(
            allow_open=False,
            allow_add=False,
            allow_reduce=True,
            allow_exit=True,
            reasons=["global_cooldown_active"],
        )
    return RiskAllowance(
        allow_open=True,
        allow_add=True,
        allow_reduce=True,
        allow_exit=True,
        reasons=[],
    )


def decide_action(
    signal: SignalVerdict,
    allowance: RiskAllowance,
    *,
    prefer_defensive_on_uncertain: bool = True,
) -> ExecutionPlan:
    """动作决策（简化版）：示例用，实际可替换为更完整的策略/专家。"""

    reasons: List[str] = list(allowance.reasons)

    if signal.verdict == "reject":
        if allowance.allow_reduce:
            return ExecutionPlan(
                action="reduce",
                direction="neutral",
                allowance=allowance,
                confidence=signal.confidence,
                notes="信号被否定：优先风险降低。",
            )
        return ExecutionPlan(
            action="hold",
            direction="neutral",
            allowance=allowance,
            confidence=signal.confidence,
            notes="信号被否定：但不允许减仓，保持观望。",
        )

    if signal.verdict == "uncertain" and prefer_defensive_on_uncertain:
        if allowance.allow_reduce:
            return ExecutionPlan(
                action="reduce",
                direction="neutral",
                allowance=allowance,
                confidence=Confidence(level="low", score=min(signal.confidence.score, 0.45)),
                notes="信号不确定：默认防御性减仓。",
            )
        return ExecutionPlan(
            action="hold",
            direction="neutral",
            allowance=allowance,
            confidence=Confidence(level="low", score=min(signal.confidence.score, 0.45)),
            notes="信号不确定：保持观望。",
        )

    if signal.verdict == "accept":
        if allowance.allow_add:
            return ExecutionPlan(
                action="add",
                direction=signal.direction,
                allowance=allowance,
                confidence=signal.confidence,
                notes="信号成立：允许加仓。",
            )
        return ExecutionPlan(
            action="hold",
            direction=signal.direction,
            allowance=allowance,
            confidence=signal.confidence,
            notes="信号成立：但系统不允许加仓，保持观望。",
        )

    return ExecutionPlan(
        action="hold",
        direction="neutral",
        allowance=allowance,
        confidence=signal.confidence,
        notes="默认保护：保持观望。",
    )
