from __future__ import annotations

import time
from typing import Any, Dict, List


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def build_symbol_memory_summary(
    *,
    exchange: str,
    symbol: str,
    raw_records: List[Dict[str, Any]],
    window: int = 50,
    now_ms: int | None = None,
) -> Dict[str, Any]:
    """规则化 symbol 记忆摘要：面向 agent 可消费上下文。"""

    now = int(now_ms or time.time() * 1000)
    ex = str(exchange or "").strip().lower()
    sym = str(symbol or "").strip().upper()

    records = [dict(item) for item in list(raw_records or []) if isinstance(item, dict)]
    records.sort(key=lambda x: _to_int(x.get("ts"), 0))
    if window > 0 and len(records) > window:
        records = records[-window:]

    signal_direction_count = {"long": 0, "short": 0, "neutral": 0}
    signal_verdict_count = {"accept": 0, "reject": 0, "uncertain": 0}
    plan_action_count: Dict[str, int] = {}
    contract_warning_count = 0
    contract_warning_event_count = 0
    contract_warning_type_count: Dict[str, int] = {}

    for rec in records:
        signal = _safe_dict(rec.get("signal"))
        plan = _safe_dict(rec.get("plan"))
        warnings = [str(x) for x in list(rec.get("contract_warnings") or []) if str(x or "").strip()]
        direction = str(signal.get("direction") or "neutral").strip().lower()
        if direction == "none":
            direction = "neutral"
        verdict = str(signal.get("verdict") or "uncertain").strip().lower()
        action = str(plan.get("action") or "hold").strip().lower()
        if direction not in signal_direction_count:
            direction = "neutral"
        if verdict not in signal_verdict_count:
            verdict = "uncertain"
        signal_direction_count[direction] += 1
        signal_verdict_count[verdict] += 1
        plan_action_count[action] = int(plan_action_count.get(action, 0)) + 1
        if warnings:
            contract_warning_event_count += 1
        contract_warning_count += len(warnings)
        for warn in warnings:
            contract_warning_type_count[warn] = int(contract_warning_type_count.get(warn, 0)) + 1

    trend_bias = "neutral"
    if signal_direction_count["long"] > signal_direction_count["short"]:
        trend_bias = "bullish"
    elif signal_direction_count["short"] > signal_direction_count["long"]:
        trend_bias = "bearish"

    latest = records[-1] if records else {}
    latest_signal = _safe_dict(latest.get("signal"))
    latest_plan = _safe_dict(latest.get("plan"))
    recent_contract_warning_types: List[str] = []
    seen = set()
    for rec in reversed(records):
        warnings = [str(x) for x in list(rec.get("contract_warnings") or []) if str(x or "").strip()]
        for warn in warnings:
            if warn in seen:
                continue
            seen.add(warn)
            recent_contract_warning_types.append(warn)
            if len(recent_contract_warning_types) >= 5:
                break
        if len(recent_contract_warning_types) >= 5:
            break

    return {
        "exchange": ex,
        "symbol": sym,
        "event_count": len(records),
        "window_size": int(max(1, window)),
        "last_decision_ts": _to_int(latest.get("ts"), now),
        "last_event_id": str(latest.get("event_id") or ""),
        "last_signal_direction": (
            "neutral"
            if str(latest_signal.get("direction") or "neutral").strip().lower() == "none"
            else str(latest_signal.get("direction") or "neutral")
        ),
        "last_signal_verdict": str(latest_signal.get("verdict") or "unknown"),
        "last_plan_action": str(latest_plan.get("action") or "hold"),
        "last_plan_direction": (
            "neutral"
            if str(latest_plan.get("direction") or "neutral").strip().lower() == "none"
            else str(latest_plan.get("direction") or "neutral")
        ),
        "signal_direction_count": signal_direction_count,
        "signal_verdict_count": signal_verdict_count,
        "plan_action_count": plan_action_count,
        "contract_warning_count": int(contract_warning_count),
        "contract_warning_event_count": int(contract_warning_event_count),
        "contract_warning_type_count": contract_warning_type_count,
        "recent_contract_warning_types": recent_contract_warning_types,
        "trend_bias": trend_bias,
        "updated_ts": now,
    }
