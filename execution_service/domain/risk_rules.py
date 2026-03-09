from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from execution_service.domain.contracts import DecisionIntent


@dataclass(frozen=True)
class RiskContext:
    """执行裁决所需的状态快照。"""

    position_state: Dict[str, Any]
    account_state: Dict[str, Any]
    risk_policy: Dict[str, Any]


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def evaluate_risk_rules(
    decision: DecisionIntent,
    context: RiskContext,
) -> Dict[str, Any]:
    """按固定优先级评估风险规则，输出确定性动作建议。"""

    position_side = str(context.position_state.get("position_side", "flat")).lower()
    position_size = _to_float(context.position_state.get("position_size"), 0.0)
    position_mode = str(
        context.risk_policy.get("position_mode", context.position_state.get("position_mode", "one_way"))
    ).strip().lower()
    allow_dual_side = bool(context.risk_policy.get("allow_dual_side", position_mode == "hedge"))
    long_position_size = _extract_leg_size(
        leg="long",
        position_state=context.position_state,
        fallback_side=position_side,
        fallback_size=position_size,
    )
    short_position_size = _extract_leg_size(
        leg="short",
        position_state=context.position_state,
        fallback_side=position_side,
        fallback_size=position_size,
    )
    max_position_size = _to_float(
        context.risk_policy.get(
            "max_position_size",
            context.position_state.get("max_position_size", 1.0),
        ),
        1.0,
    )
    max_long_position_size = _to_float(
        context.risk_policy.get("max_long_position_size", max_position_size),
        max_position_size,
    )
    max_short_position_size = _to_float(
        context.risk_policy.get("max_short_position_size", max_position_size),
        max_position_size,
    )
    cooldown_seconds_left = _to_int(
        context.position_state.get("cooldown_seconds_left"),
        0,
    )
    current_drawdown_ratio = _to_float(
        context.account_state.get("current_drawdown_ratio"),
        0.0,
    )
    max_drawdown_ratio = _to_float(
        context.risk_policy.get(
            "max_drawdown_ratio",
            context.account_state.get("max_drawdown_ratio", 1.0),
        ),
        1.0,
    )

    direction = decision.direction_intent

    # 规则 1: 仓位上限（最高优先级）
    if direction == "long" and long_position_size >= max_long_position_size:
        return {
            "execution_action": "skip",
            "reject_reason": "position_limit_reached",
            "applied_risk_rules": ["max_position_limit_long"],
            "notes": "多头仓位已达上限，禁止继续加仓",
        }
    if direction == "short" and short_position_size >= max_short_position_size:
        return {
            "execution_action": "skip",
            "reject_reason": "position_limit_reached",
            "applied_risk_rules": ["max_position_limit_short"],
            "notes": "空头仓位已达上限，禁止继续加仓",
        }

    # 规则 2: 冷却期
    if cooldown_seconds_left > 0:
        return {
            "execution_action": "skip",
            "reject_reason": "cooldown_active",
            "applied_risk_rules": ["cooldown"],
            "notes": f"当前处于冷却期，剩余 {cooldown_seconds_left} 秒",
        }

    # 规则 3: 最大回撤阈值
    if current_drawdown_ratio >= max_drawdown_ratio:
        return {
            "execution_action": "skip",
            "reject_reason": "max_drawdown_exceeded",
            "applied_risk_rules": ["max_drawdown"],
            "notes": "当前回撤超过阈值，禁止新增风险",
        }

    # 规则 4: 方向冲突（有持仓且与意图方向相反）
    if (
        not allow_dual_side
        and
        direction in {"long", "short"}
        and position_side in {"long", "short"}
        and direction != position_side
        and position_size > 0
    ):
        return {
            "execution_action": "reduce",
            "reject_reason": "direction_conflict_with_position",
            "applied_risk_rules": ["direction_conflict"],
            "notes": "当前持仓方向与新意图冲突，先减仓再观察",
        }

    # 规则 5: 双向模式（hedge）允许同 symbol 多空并存，按腿独立加仓
    if allow_dual_side and direction in {"long", "short"}:
        return {
            "execution_action": "add",
            "reject_reason": None,
            "applied_risk_rules": ["dual_side_hedge_mode"],
            "notes": "双向持仓模式，按目标方向独立执行",
        }

    if direction == "none":
        return {
            "execution_action": "hold",
            "reject_reason": None,
            "applied_risk_rules": [],
            "notes": "无方向意图，保持观望",
        }

    return {
        "execution_action": "add",
        "reject_reason": None,
        "applied_risk_rules": [],
        "notes": "通过风控检查，允许执行",
    }


def _extract_leg_size(
    *,
    leg: str,
    position_state: Dict[str, Any],
    fallback_side: str,
    fallback_size: float,
) -> float:
    leg_key = f"{leg}_position_size"
    if leg_key in position_state:
        return _to_float(position_state.get(leg_key), 0.0)
    legs = position_state.get("legs")
    if isinstance(legs, dict):
        leg_payload = legs.get(leg)
        if isinstance(leg_payload, dict):
            return _to_float(leg_payload.get("position_size", leg_payload.get("qty")), 0.0)
    if fallback_side == leg:
        return max(0.0, fallback_size)
    return 0.0
