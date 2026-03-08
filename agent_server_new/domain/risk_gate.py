from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .contracts import RiskAllowance


@dataclass(frozen=True)
class RiskGateContext:
    """风险门控上下文：更偏账户/仓位风险，不承载策略语义。"""

    global_regime: Literal["normal", "elevated", "critical"]
    cooldown_active: bool


def risk_gate(ctx: RiskGateContext) -> RiskAllowance:
    """风险门控：示例实现，后续可接入 max position/exposure/margin 等硬约束。"""

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

