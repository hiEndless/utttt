from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from execution_service.domain.contracts import DecisionIntent
from execution_service.domain.risk_check_builder import build_risk_checks
from execution_service.domain.risk_result_builder import build_risk_decision_result


@dataclass(frozen=True)
class RiskContext:
    """执行裁决所需的状态快照。"""

    position_state: Dict[str, Any]
    account_state: Dict[str, Any]
    risk_policy: Dict[str, Any]


# 中文注释：默认优先级冻结，确保不配置时行为稳定可预期。
RULE_POSITION_LIMIT = "position_limit"
RULE_COOLDOWN = "cooldown"
RULE_MAX_DRAWDOWN = "max_drawdown"
RULE_ACCOUNT_NOTIONAL = "account_notional"
RULE_MARGIN_RATIO = "margin_ratio"
RULE_DAILY_LOSS = "daily_loss"
RULE_CONSECUTIVE_LOSS = "consecutive_loss"
RULE_DIRECTION_CONFLICT = "direction_conflict"

DEFAULT_RULE_PRIORITY_ORDER = (
    RULE_POSITION_LIMIT,
    RULE_COOLDOWN,
    RULE_MAX_DRAWDOWN,
    RULE_ACCOUNT_NOTIONAL,
    RULE_MARGIN_RATIO,
    RULE_DAILY_LOSS,
    RULE_CONSECUTIVE_LOSS,
    RULE_DIRECTION_CONFLICT,
)


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
    margin_ratio = _to_float(context.account_state.get("margin_ratio"), 0.0)
    daily_loss = _resolve_daily_loss(context.account_state)
    consecutive_loss_count = _to_float(context.account_state.get("consecutive_loss_count"), 0.0)
    min_available_balance = _to_float(context.risk_policy.get("min_available_balance"), 0.0)
    account_equity = _to_float(context.account_state.get("account_equity"), 0.0)
    gross_position_size = max(0.0, long_position_size) + max(0.0, short_position_size)
    account_notional = _to_float(
        context.position_state.get("gross_notional", context.position_state.get("account_notional", gross_position_size)),
        gross_position_size,
    )
    max_account_notional = _to_float(context.risk_policy.get("max_account_notional"), 1_000_000_000.0)
    max_margin_ratio = _to_float(context.risk_policy.get("max_margin_ratio"), 1.0)
    max_daily_loss = _to_float(context.risk_policy.get("max_daily_loss"), 1_000_000_000.0)
    max_consecutive_loss_count = _to_float(context.risk_policy.get("max_consecutive_loss_count"), 1_000_000_000.0)
    symbol_exposure_ratio = _resolve_symbol_exposure_ratio(
        context=context,
        gross_position_size=gross_position_size,
        account_equity=account_equity,
    )
    max_symbol_exposure_ratio = _to_float(context.risk_policy.get("max_symbol_exposure_ratio"), 1.0)

    direction = decision.direction_intent
    risk_checks = build_risk_checks(
        direction=direction,
        long_position_size=long_position_size,
        short_position_size=short_position_size,
        max_long_position_size=max_long_position_size,
        max_short_position_size=max_short_position_size,
        current_drawdown_ratio=current_drawdown_ratio,
        max_drawdown_ratio=max_drawdown_ratio,
        available_balance=available_balance,
        min_available_balance=min_available_balance,
        account_notional=account_notional,
        max_account_notional=max_account_notional,
        margin_ratio=margin_ratio,
        max_margin_ratio=max_margin_ratio,
        daily_loss=daily_loss,
        max_daily_loss=max_daily_loss,
        consecutive_loss_count=consecutive_loss_count,
        max_consecutive_loss_count=max_consecutive_loss_count,
        symbol_exposure_ratio=symbol_exposure_ratio,
        max_symbol_exposure_ratio=max_symbol_exposure_ratio,
    )
    rule_priority_order = _resolve_rule_priority_order(context.risk_policy)

    def _finalize(
        *,
        execution_action: str,
        reject_reason: str | None,
        applied_risk_rules: list[str],
        notes: str,
        hit_rule: str | None = None,
        hit_rule_value: float | None = None,
        hit_rule_threshold: float | None = None,
    ) -> Dict[str, Any]:
        return build_risk_decision_result(
            decision=decision,
            account_id=str(context.account_state.get("account_id") or "main"),
            direction=direction,
            position_side=position_side,
            allow_dual_side=allow_dual_side,
            long_position_size=long_position_size,
            short_position_size=short_position_size,
            step_size=_resolve_step_size(context=context),
            risk_checks=list(risk_checks),
            execution_action=execution_action,
            reject_reason=reject_reason,
            applied_risk_rules=applied_risk_rules,
            notes=notes,
            rule_priority_order=list(rule_priority_order),
            hit_rule=hit_rule,
            hit_rule_value=hit_rule_value,
            hit_rule_threshold=hit_rule_threshold,
        )

    rule_handlers: Dict[str, Callable[[], Dict[str, Any] | None]] = {
        RULE_POSITION_LIMIT: lambda: _check_rule_position_limit(
            direction=direction,
            long_position_size=long_position_size,
            short_position_size=short_position_size,
            max_long_position_size=max_long_position_size,
            max_short_position_size=max_short_position_size,
        ),
        RULE_COOLDOWN: lambda: _check_rule_cooldown(cooldown_seconds_left=cooldown_seconds_left),
        RULE_MAX_DRAWDOWN: lambda: _check_rule_max_drawdown(
            current_drawdown_ratio=current_drawdown_ratio,
            max_drawdown_ratio=max_drawdown_ratio,
        ),
        RULE_ACCOUNT_NOTIONAL: lambda: _check_rule_account_notional(
            account_notional=account_notional,
            max_account_notional=max_account_notional,
        ),
        RULE_MARGIN_RATIO: lambda: _check_rule_margin_ratio(
            margin_ratio=margin_ratio,
            max_margin_ratio=max_margin_ratio,
        ),
        RULE_DAILY_LOSS: lambda: _check_rule_daily_loss(
            daily_loss=daily_loss,
            max_daily_loss=max_daily_loss,
        ),
        RULE_CONSECUTIVE_LOSS: lambda: _check_rule_consecutive_loss(
            consecutive_loss_count=consecutive_loss_count,
            max_consecutive_loss_count=max_consecutive_loss_count,
        ),
        RULE_DIRECTION_CONFLICT: lambda: _check_rule_direction_conflict(
            allow_dual_side=allow_dual_side,
            direction=direction,
            position_side=position_side,
            position_size=position_size,
        ),
    }
    for rule_name in rule_priority_order:
        result = rule_handlers[rule_name]()
        if result is not None:
            return _finalize(**result)

    # 规则 5: 双向模式（hedge）允许同 symbol 多空并存，按腿独立加仓
    if allow_dual_side and direction in {"long", "short"}:
        return _finalize(
            execution_action="add",
            reject_reason=None,
            applied_risk_rules=["dual_side_hedge_mode"],
            notes="双向持仓模式，按目标方向独立执行",
            hit_rule="dual_side_hedge_mode",
        )

    if direction == "none":
        return _finalize(
            execution_action="hold",
            reject_reason=None,
            applied_risk_rules=[],
            notes="无方向意图，保持观望",
            hit_rule="none_intent",
        )

    return _finalize(
        execution_action="add",
        reject_reason=None,
        applied_risk_rules=[],
        notes="通过风控检查，允许执行",
        hit_rule="passed_all_rules",
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


def _resolve_daily_loss(account_state: Dict[str, Any]) -> float:
    explicit_daily_loss = account_state.get("daily_loss")
    if explicit_daily_loss is not None:
        return max(0.0, _to_float(explicit_daily_loss, 0.0))
    daily_realized_pnl = _to_float(account_state.get("daily_realized_pnl"), 0.0)
    return max(0.0, -daily_realized_pnl)


def _resolve_rule_priority_order(risk_policy: Dict[str, Any]) -> tuple[str, ...]:
    raw = risk_policy.get("rule_priority_order")
    if not isinstance(raw, list):
        return DEFAULT_RULE_PRIORITY_ORDER
    candidate = [str(x).strip() for x in raw if str(x).strip()]
    if len(candidate) != len(DEFAULT_RULE_PRIORITY_ORDER):
        return DEFAULT_RULE_PRIORITY_ORDER
    if len(set(candidate)) != len(DEFAULT_RULE_PRIORITY_ORDER):
        return DEFAULT_RULE_PRIORITY_ORDER
    if set(candidate) != set(DEFAULT_RULE_PRIORITY_ORDER):
        return DEFAULT_RULE_PRIORITY_ORDER
    return tuple(candidate)


def _check_rule_position_limit(
    *,
    direction: str,
    long_position_size: float,
    short_position_size: float,
    max_long_position_size: float,
    max_short_position_size: float,
) -> Dict[str, Any] | None:
    if direction == "long" and long_position_size >= max_long_position_size:
        return {
            "execution_action": "skip",
            "reject_reason": "position_limit_reached",
            "applied_risk_rules": ["max_position_limit_long"],
            "notes": "多头仓位已达上限，禁止继续加仓",
            "hit_rule": RULE_POSITION_LIMIT,
            "hit_rule_value": long_position_size,
            "hit_rule_threshold": max_long_position_size,
        }
    if direction == "short" and short_position_size >= max_short_position_size:
        return {
            "execution_action": "skip",
            "reject_reason": "position_limit_reached",
            "applied_risk_rules": ["max_position_limit_short"],
            "notes": "空头仓位已达上限，禁止继续加仓",
            "hit_rule": RULE_POSITION_LIMIT,
            "hit_rule_value": short_position_size,
            "hit_rule_threshold": max_short_position_size,
        }
    return None


def _check_rule_cooldown(*, cooldown_seconds_left: int) -> Dict[str, Any] | None:
    if cooldown_seconds_left > 0:
        return {
            "execution_action": "skip",
            "reject_reason": "cooldown_active",
            "applied_risk_rules": ["cooldown"],
            "notes": f"当前处于冷却期，剩余 {cooldown_seconds_left} 秒",
            "hit_rule": RULE_COOLDOWN,
            "hit_rule_value": float(cooldown_seconds_left),
            "hit_rule_threshold": 0.0,
        }
    return None


def _check_rule_max_drawdown(
    *,
    current_drawdown_ratio: float,
    max_drawdown_ratio: float,
) -> Dict[str, Any] | None:
    if current_drawdown_ratio >= max_drawdown_ratio:
        return {
            "execution_action": "skip",
            "reject_reason": "max_drawdown_exceeded",
            "applied_risk_rules": ["max_drawdown"],
            "notes": "当前回撤超过阈值，禁止新增风险",
            "hit_rule": RULE_MAX_DRAWDOWN,
            "hit_rule_value": current_drawdown_ratio,
            "hit_rule_threshold": max_drawdown_ratio,
        }
    return None


def _check_rule_direction_conflict(
    *,
    allow_dual_side: bool,
    direction: str,
    position_side: str,
    position_size: float,
) -> Dict[str, Any] | None:
    if (
        not allow_dual_side
        and direction in {"long", "short"}
        and position_side in {"long", "short"}
        and direction != position_side
        and position_size > 0
    ):
        return {
            "execution_action": "reduce",
            "reject_reason": "direction_conflict_with_position",
            "applied_risk_rules": ["direction_conflict"],
            "notes": "当前持仓方向与新意图冲突，先减仓再观察",
            "hit_rule": RULE_DIRECTION_CONFLICT,
        }
    return None


def _check_rule_account_notional(
    *,
    account_notional: float,
    max_account_notional: float,
) -> Dict[str, Any] | None:
    if account_notional > max_account_notional:
        return {
            "execution_action": "skip",
            "reject_reason": "account_notional_exceeded",
            "applied_risk_rules": ["account_notional_limit"],
            "notes": "账户总敞口超过阈值，禁止新增风险",
            "hit_rule": RULE_ACCOUNT_NOTIONAL,
            "hit_rule_value": account_notional,
            "hit_rule_threshold": max_account_notional,
        }
    return None


def _check_rule_margin_ratio(
    *,
    margin_ratio: float,
    max_margin_ratio: float,
) -> Dict[str, Any] | None:
    if margin_ratio > max_margin_ratio:
        return {
            "execution_action": "skip",
            "reject_reason": "account_margin_ratio_exceeded",
            "applied_risk_rules": ["account_margin_ratio_limit"],
            "notes": "账户保证金率超过阈值，禁止新增风险",
            "hit_rule": RULE_MARGIN_RATIO,
            "hit_rule_value": margin_ratio,
            "hit_rule_threshold": max_margin_ratio,
        }
    return None


def _check_rule_daily_loss(
    *,
    daily_loss: float,
    max_daily_loss: float,
) -> Dict[str, Any] | None:
    if daily_loss > max_daily_loss:
        return {
            "execution_action": "skip",
            "reject_reason": "daily_loss_exceeded",
            "applied_risk_rules": ["account_daily_loss_limit"],
            "notes": "账户当日亏损超过阈值，禁止新增风险",
            "hit_rule": RULE_DAILY_LOSS,
            "hit_rule_value": daily_loss,
            "hit_rule_threshold": max_daily_loss,
        }
    return None


def _check_rule_consecutive_loss(
    *,
    consecutive_loss_count: float,
    max_consecutive_loss_count: float,
) -> Dict[str, Any] | None:
    if consecutive_loss_count > max_consecutive_loss_count:
        return {
            "execution_action": "skip",
            "reject_reason": "consecutive_loss_exceeded",
            "applied_risk_rules": ["account_consecutive_loss_limit"],
            "notes": "账户连续亏损次数超过阈值，禁止新增风险",
            "hit_rule": RULE_CONSECUTIVE_LOSS,
            "hit_rule_value": consecutive_loss_count,
            "hit_rule_threshold": max_consecutive_loss_count,
        }
    return None
