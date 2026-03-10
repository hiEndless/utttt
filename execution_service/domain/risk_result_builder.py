from __future__ import annotations

import time
from typing import Any, Dict, List

from execution_service.domain.contracts import DecisionIntent
from execution_service.domain.risk_state_change_reasons import (
    RISK_STATE_CHANGE_REASON_DEFAULT_NORMAL,
    RISK_STATE_CHANGE_REASON_ZH,
)
from execution_service.domain.risk_states import RISK_STATE_NORMAL


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
    rule_priority_order: List[str] | None = None,
    hit_rule: str | None = None,
    hit_rule_value: float | None = None,
    hit_rule_threshold: float | None = None,
    evaluation_trace: List[Dict[str, Any]] | None = None,
    risk_state: str | None = None,
    previous_risk_state: str | None = None,
    risk_state_change_reason: str | None = None,
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
    rule_debug = {
        "hit_rule": str(hit_rule or "none"),
        "rule_priority_order": list(rule_priority_order or []),
        "hit_rule_value": hit_rule_value,
        "hit_rule_threshold": hit_rule_threshold,
        # 中文注释：记录风险状态迁移，便于排查风控状态抖动与回放时序。
        "previous_risk_state": str(previous_risk_state or RISK_STATE_NORMAL),
        "current_risk_state": str(risk_state or RISK_STATE_NORMAL),
        "risk_state_changed": str(previous_risk_state or RISK_STATE_NORMAL) != str(risk_state or RISK_STATE_NORMAL),
        "risk_state_change_reason": str(risk_state_change_reason or RISK_STATE_CHANGE_REASON_DEFAULT_NORMAL),
        "risk_state_change_reason_zh": RISK_STATE_CHANGE_REASON_ZH.get(
            str(risk_state_change_reason or RISK_STATE_CHANGE_REASON_DEFAULT_NORMAL),
            RISK_STATE_CHANGE_REASON_ZH[RISK_STATE_CHANGE_REASON_DEFAULT_NORMAL],
        ),
        "matched_at_ms": int(time.time() * 1000),
        "evaluation_trace": list(evaluation_trace or []),
    }
    return {
        "execution_action": execution_action,
        "reject_reason": reject_reason,
        "applied_risk_rules": applied_risk_rules,
        "signal_result": {
            "signal_action": signal_action,
            "risk_state": str(risk_state or RISK_STATE_NORMAL),
            "mode": "simulated",
            "scope": {
                "exchange": decision.exchange,
                "account_id": account_id,
                "symbol": decision.symbol,
            },
            "position_before": position_before,
            "position_after_simulation": position_after,
            "risk_checks": list(risk_checks),
            "rule_debug": rule_debug,
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
