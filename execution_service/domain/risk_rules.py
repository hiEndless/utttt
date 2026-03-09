from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from execution_service.domain.contracts import DecisionIntent
from execution_service.domain.risk_check_codes import (
    RISK_CHECK_ACCOUNT_AVAILABLE_BALANCE,
    RISK_CHECK_ACCOUNT_DRAWDOWN_LIMIT,
    RISK_CHECK_LONG_LEG_POSITION_LIMIT,
    RISK_CHECK_SHORT_LEG_POSITION_LIMIT,
    RISK_CHECK_SYMBOL_EXPOSURE_RATIO,
)


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
    available_balance = _to_float(context.account_state.get("available_balance"), 0.0)
    min_available_balance = _to_float(context.risk_policy.get("min_available_balance"), 0.0)
    account_equity = _to_float(context.account_state.get("account_equity"), 0.0)
    gross_position_size = max(0.0, long_position_size) + max(0.0, short_position_size)
    symbol_exposure_ratio = _resolve_symbol_exposure_ratio(
        context=context,
        gross_position_size=gross_position_size,
        account_equity=account_equity,
    )
    max_symbol_exposure_ratio = _to_float(context.risk_policy.get("max_symbol_exposure_ratio"), 1.0)

    direction = decision.direction_intent
    risk_checks = _build_risk_checks(
        direction=direction,
        long_position_size=long_position_size,
        short_position_size=short_position_size,
        max_long_position_size=max_long_position_size,
        max_short_position_size=max_short_position_size,
        current_drawdown_ratio=current_drawdown_ratio,
        max_drawdown_ratio=max_drawdown_ratio,
        available_balance=available_balance,
        min_available_balance=min_available_balance,
        symbol_exposure_ratio=symbol_exposure_ratio,
        max_symbol_exposure_ratio=max_symbol_exposure_ratio,
    )

    def _finalize(
        *,
        execution_action: str,
        reject_reason: str | None,
        applied_risk_rules: list[str],
        notes: str,
    ) -> Dict[str, Any]:
        signal_action = _build_signal_action(
            execution_action=execution_action,
            direction=direction,
            position_side=position_side,
            allow_dual_side=allow_dual_side,
        )
        position_before = {
            "mode": "hedge" if allow_dual_side else "one_way",
            "long_position_size": long_position_size,
            "short_position_size": short_position_size,
            "net_position_size": long_position_size - short_position_size,
        }
        position_after = _simulate_position_after(
            signal_action=signal_action,
            long_position_size=long_position_size,
            short_position_size=short_position_size,
            step_size=_resolve_step_size(context=context),
        )
        return {
            "execution_action": execution_action,
            "reject_reason": reject_reason,
            "applied_risk_rules": applied_risk_rules,
            "signal_result": {
                "signal_action": signal_action,
                "mode": "simulated",
                "scope": {
                    "exchange": decision.exchange,
                    "account_id": str(context.account_state.get("account_id") or "main"),
                    "symbol": decision.symbol,
                },
                "position_before": position_before,
                "position_after_simulation": position_after,
                "risk_checks": list(risk_checks),
            },
            "notes": notes,
        }

    # 规则 1: 仓位上限（最高优先级）
    if direction == "long" and long_position_size >= max_long_position_size:
        return _finalize(
            execution_action="skip",
            reject_reason="position_limit_reached",
            applied_risk_rules=["max_position_limit_long"],
            notes="多头仓位已达上限，禁止继续加仓",
        )
    if direction == "short" and short_position_size >= max_short_position_size:
        return _finalize(
            execution_action="skip",
            reject_reason="position_limit_reached",
            applied_risk_rules=["max_position_limit_short"],
            notes="空头仓位已达上限，禁止继续加仓",
        )

    # 规则 2: 冷却期
    if cooldown_seconds_left > 0:
        return _finalize(
            execution_action="skip",
            reject_reason="cooldown_active",
            applied_risk_rules=["cooldown"],
            notes=f"当前处于冷却期，剩余 {cooldown_seconds_left} 秒",
        )

    # 规则 3: 最大回撤阈值
    if current_drawdown_ratio >= max_drawdown_ratio:
        return _finalize(
            execution_action="skip",
            reject_reason="max_drawdown_exceeded",
            applied_risk_rules=["max_drawdown"],
            notes="当前回撤超过阈值，禁止新增风险",
        )

    # 规则 4: 方向冲突（有持仓且与意图方向相反）
    if (
        not allow_dual_side
        and
        direction in {"long", "short"}
        and position_side in {"long", "short"}
        and direction != position_side
        and position_size > 0
    ):
        return _finalize(
            execution_action="reduce",
            reject_reason="direction_conflict_with_position",
            applied_risk_rules=["direction_conflict"],
            notes="当前持仓方向与新意图冲突，先减仓再观察",
        )

    # 规则 5: 双向模式（hedge）允许同 symbol 多空并存，按腿独立加仓
    if allow_dual_side and direction in {"long", "short"}:
        return _finalize(
            execution_action="add",
            reject_reason=None,
            applied_risk_rules=["dual_side_hedge_mode"],
            notes="双向持仓模式，按目标方向独立执行",
        )

    if direction == "none":
        return _finalize(
            execution_action="hold",
            reject_reason=None,
            applied_risk_rules=[],
            notes="无方向意图，保持观望",
        )

    return _finalize(
        execution_action="add",
        reject_reason=None,
        applied_risk_rules=[],
        notes="通过风控检查，允许执行",
    )


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


def _resolve_step_size(*, context: RiskContext) -> float:
    step = _to_float(context.risk_policy.get("simulation_step_size"), 0.1)
    if step <= 0:
        return 0.1
    return step


def _build_signal_action(
    *,
    execution_action: str,
    direction: str,
    position_side: str,
    allow_dual_side: bool,
) -> str:
    if execution_action == "add":
        if direction == "long":
            return "add_long"
        if direction == "short":
            return "add_short"
        return "hold"
    if execution_action == "reduce":
        if allow_dual_side:
            if direction == "long":
                return "reduce_short"
            if direction == "short":
                return "reduce_long"
        if position_side == "long":
            return "reduce_long"
        if position_side == "short":
            return "reduce_short"
        return "hold"
    if execution_action == "exit":
        return "exit_all"
    if execution_action == "skip":
        return "skip"
    return "hold"


def _simulate_position_after(
    *,
    signal_action: str,
    long_position_size: float,
    short_position_size: float,
    step_size: float,
) -> Dict[str, float]:
    long_after = max(0.0, long_position_size)
    short_after = max(0.0, short_position_size)
    if signal_action == "add_long":
        long_after += step_size
    elif signal_action == "add_short":
        short_after += step_size
    elif signal_action == "reduce_long":
        long_after = max(0.0, long_after - step_size)
    elif signal_action == "reduce_short":
        short_after = max(0.0, short_after - step_size)
    elif signal_action == "exit_all":
        long_after = 0.0
        short_after = 0.0
    return {
        "long_position_size": long_after,
        "short_position_size": short_after,
        "net_position_size": long_after - short_after,
    }


def _resolve_symbol_exposure_ratio(
    *,
    context: RiskContext,
    gross_position_size: float,
    account_equity: float,
) -> float:
    explicit = context.position_state.get("symbol_exposure_ratio")
    if explicit is not None:
        return _to_float(explicit, 0.0)
    if account_equity <= 0:
        return 0.0
    return gross_position_size / account_equity


def _build_risk_checks(
    *,
    direction: str,
    long_position_size: float,
    short_position_size: float,
    max_long_position_size: float,
    max_short_position_size: float,
    current_drawdown_ratio: float,
    max_drawdown_ratio: float,
    available_balance: float,
    min_available_balance: float,
    symbol_exposure_ratio: float,
    max_symbol_exposure_ratio: float,
) -> list[Dict[str, Any]]:
    checks: list[Dict[str, Any]] = [
        {
            "check": RISK_CHECK_ACCOUNT_DRAWDOWN_LIMIT,
            "scope": "account",
            "status": _status(current_drawdown_ratio < max_drawdown_ratio),
            "value": current_drawdown_ratio,
            "threshold": max_drawdown_ratio,
            "message_zh": f"账户回撤检查: 当前={current_drawdown_ratio:.4f}, 阈值={max_drawdown_ratio:.4f}",
        },
        {
            "check": RISK_CHECK_ACCOUNT_AVAILABLE_BALANCE,
            "scope": "account",
            "status": _status(available_balance >= min_available_balance),
            "value": available_balance,
            "threshold": min_available_balance,
            "message_zh": f"可用余额检查: 当前={available_balance:.4f}, 阈值={min_available_balance:.4f}",
        },
        {
            "check": RISK_CHECK_SYMBOL_EXPOSURE_RATIO,
            "scope": "symbol",
            "status": _status(symbol_exposure_ratio <= max_symbol_exposure_ratio),
            "value": symbol_exposure_ratio,
            "threshold": max_symbol_exposure_ratio,
            "message_zh": f"symbol 暴露占比检查: 当前={symbol_exposure_ratio:.4f}, 阈值={max_symbol_exposure_ratio:.4f}",
        },
    ]
    if direction == "long":
        checks.append(
            {
                "check": RISK_CHECK_LONG_LEG_POSITION_LIMIT,
                "scope": "position",
                "status": _status(long_position_size < max_long_position_size),
                "value": long_position_size,
                "threshold": max_long_position_size,
                "message_zh": f"多头仓位上限检查: 当前={long_position_size:.4f}, 阈值={max_long_position_size:.4f}",
            }
        )
    if direction == "short":
        checks.append(
            {
                "check": RISK_CHECK_SHORT_LEG_POSITION_LIMIT,
                "scope": "position",
                "status": _status(short_position_size < max_short_position_size),
                "value": short_position_size,
                "threshold": max_short_position_size,
                "message_zh": f"空头仓位上限检查: 当前={short_position_size:.4f}, 阈值={max_short_position_size:.4f}",
            }
        )
    return checks


def _status(passed: bool) -> str:
    return "pass" if passed else "fail"
