from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple


# 动作策略层：把“硬规则 allowed_actions”转换为 LLM 输出动作的可执行约束，并在必要时强制降级


LLM_ACTIONS: Set[str] = {"ADD_POSITION", "HOLD", "DEFENSIVE", "REDUCE", "EXIT"}


@dataclass(frozen=True)
class AllowedLLMPolicy:
    allowed_llm_actions: Set[str]
    max_add_pct: Optional[float] = None
    forbid_add: bool = False


def derive_allowed_llm_policy(risk_rules_decision: Dict[str, Any] | None) -> AllowedLLMPolicy:
    allowed_actions = set((risk_rules_decision or {}).get("allowed_actions") or [])

    forbid_add = any(x in allowed_actions for x in ("HOLD_NO_ADD", "HOLD_REDUCE_ONLY"))

    allowed_llm_actions: Set[str] = {"HOLD", "DEFENSIVE"}

    if any(x in allowed_actions for x in ("REDUCE", "REDUCE_OPTIONAL")):
        allowed_llm_actions.add("REDUCE")
    if any(x in allowed_actions for x in ("CLOSE", "CLOSE_OPTIONAL")):
        allowed_llm_actions.add("EXIT")

    max_add_pct: Optional[float] = None
    if not forbid_add:
        if "ADD" in allowed_actions:
            allowed_llm_actions.add("ADD_POSITION")
        elif "ADD_CAUTIOUS" in allowed_actions:
            allowed_llm_actions.add("ADD_POSITION")
            max_add_pct = 0.2

    return AllowedLLMPolicy(
        allowed_llm_actions=allowed_llm_actions,
        max_add_pct=max_add_pct,
        forbid_add=forbid_add,
    )


def enforce_position_risk_action(
    *,
    llm_output: Dict[str, Any],
    risk_rules_decision: Dict[str, Any] | None,
    available_exposure_pct: Optional[float] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    policy = derive_allowed_llm_policy(risk_rules_decision)
    allowed = policy.allowed_llm_actions

    adjusted = dict(llm_output or {})
    reasons: List[str] = []

    action = str(adjusted.get("recommended_action") or "HOLD").upper()
    if action not in LLM_ACTIONS:
        action = "HOLD"
        reasons.append("输出动作不在系统枚举内，已自动降级为可执行动作")

    if action not in allowed:
        fallback = _choose_fallback_action(action, allowed)
        adjusted["recommended_action"] = fallback
        action = fallback
        reasons.append("输出动作不在硬规则允许范围内，已自动降级为可执行动作")

    _normalize_fields(adjusted, action)

    if action == "ADD_POSITION":
        max_add = policy.max_add_pct
        add_pct = float(adjusted.get("add_pct") or 0.0)

        if max_add is not None and add_pct > max_add:
            adjusted["add_pct"] = max_add
            reasons.append("加仓比例超过谨慎加仓上限，已自动收敛")

        if available_exposure_pct is not None:
            try:
                avail = float(available_exposure_pct)
            except Exception:
                avail = None
            if avail is not None and avail >= 0.0 and adjusted.get("add_pct") is not None:
                if float(adjusted["add_pct"]) > avail:
                    if avail <= 0.0:
                        adjusted["recommended_action"] = "HOLD"
                        adjusted["add_pct"] = 0.0
                        adjusted["tighten_stop"] = True
                        reasons.append("可用敞口不足，已自动禁止加仓并降级为持有")
                    else:
                        adjusted["add_pct"] = avail
                        reasons.append("加仓比例超过可用敞口，已自动收敛")

    if policy.forbid_add and action != "ADD_POSITION":
        freeze = adjusted.get("freeze_add_position_min")
        try:
            freeze_int = int(freeze) if freeze is not None else 0
        except Exception:
            freeze_int = 0
        adjusted["freeze_add_position_min"] = max(freeze_int, 30)

    if reasons:
        existing = adjusted.get("reasoning")
        if not isinstance(existing, list):
            existing = []
        adjusted["reasoning"] = list(existing) + reasons

    return adjusted, reasons


def _choose_fallback_action(requested: str, allowed: Set[str]) -> str:
    if requested == "EXIT":
        if "REDUCE" in allowed:
            return "REDUCE"
        if "DEFENSIVE" in allowed:
            return "DEFENSIVE"
        return "HOLD"
    if requested == "REDUCE":
        if "DEFENSIVE" in allowed:
            return "DEFENSIVE"
        return "HOLD"
    if requested == "ADD_POSITION":
        if "DEFENSIVE" in allowed:
            return "DEFENSIVE"
        return "HOLD"
    if requested == "DEFENSIVE":
        return "HOLD" if "HOLD" in allowed else next(iter(allowed), "HOLD")
    return "HOLD" if "HOLD" in allowed else next(iter(allowed), "HOLD")


def _normalize_fields(payload: Dict[str, Any], action: str) -> None:
    if action == "EXIT":
        payload["reduce_pct"] = 1.0
        payload["add_pct"] = 0.0
        payload["tighten_stop"] = True
        return

    if action == "REDUCE":
        rp = payload.get("reduce_pct")
        try:
            rp_f = float(rp)
        except Exception:
            rp_f = 0.25
        if not (0.1 < rp_f <= 0.5):
            rp_f = 0.25
        payload["reduce_pct"] = rp_f
        payload["add_pct"] = 0.0
        return

    if action == "ADD_POSITION":
        ap = payload.get("add_pct")
        try:
            ap_f = float(ap)
        except Exception:
            ap_f = 0.2
        if not (0.1 <= ap_f <= 0.5):
            ap_f = 0.2
        payload["add_pct"] = ap_f
        payload["reduce_pct"] = 0.0
        return

    payload["reduce_pct"] = 0.0
    payload["add_pct"] = 0.0
