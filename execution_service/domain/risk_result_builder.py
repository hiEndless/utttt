from __future__ import annotations

from typing import Any, Dict, List

from execution_service.domain.contracts import DecisionIntent


def build_risk_decision_result(
    *,
    decision: DecisionIntent,
    account_id: str,
    direction: str,
    position_side: str,
    allow_dual_side: bool,
    long_position_size: float,
    short_position_size: float,
    step_size: float,
    risk_checks: List[Dict[str, Any]],
    execution_action: str,
    reject_reason: str | None,
    applied_risk_rules: List[str],
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
        step_size=step_size,
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
                "account_id": account_id,
                "symbol": decision.symbol,
            },
            "position_before": position_before,
            "position_after_simulation": position_after,
            "risk_checks": list(risk_checks),
        },
        "notes": notes,
    }


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

