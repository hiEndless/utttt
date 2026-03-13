from __future__ import annotations

"""Decision plan adapter: map signal decision to execution plan and assemble trace/memory payloads.

This module is part of the minimal decision chain and must not reintroduce
legacy intent/rule/gate/planner domain logic.
"""

from dataclasses import dataclass
from typing import Any, Dict

from services.agent_server_new.domain.contracts import Confidence, ExecutionPlan, RiskAllowance, SignalDecision
from services.agent_server_new.observability.decision_trace import DecisionTrace, map_alert_codes_from_contract_warnings

SIGNAL_DECISION_PLAN_NOTES = "minimal_pipeline_semantic_plan"


@dataclass(frozen=True)
class DecisionPlanState:
    decision_intent_snapshot: Dict[str, Any]
    allowance: RiskAllowance
    plan: ExecutionPlan


def build_decision_plan_state(
    *,
    signal: Any,
    msl: Any,  # noqa: ARG001
    position_context: Dict[str, Any],  # noqa: ARG001
    active_events: list[Dict[str, Any]],  # noqa: ARG001
    signal_event: Dict[str, Any],  # noqa: ARG001
    cross_horizon: Dict[str, str],  # noqa: ARG001
) -> DecisionPlanState:
    verdict = str(getattr(signal, "verdict", "") or "uncertain").strip().lower()
    direction = str(getattr(signal, "direction", "") or "none").strip().lower()
    is_accept = verdict == "accept" and direction in {"long", "short"}
    decision_intent_snapshot = {
        "intent": "increase" if is_accept else "hold",
        "direction": direction if is_accept else "none",
        "confidence": {
            "level": signal.confidence.level,
            "score": signal.confidence.score,
        },
        "reasons": ["signal_semantic_plan"],
        "notes": SIGNAL_DECISION_PLAN_NOTES,
    }
    allowance = RiskAllowance(
        allow_open=True,
        allow_add=True,
        allow_reduce=True,
        allow_exit=True,
        reasons=["execution_service_final_authority"],
    )
    plan = ExecutionPlan(
        action="add" if is_accept else "hold",
        direction=direction if is_accept else "none",
        allowance=allowance,
        confidence=signal.confidence,
        sizing=None,
        notes=SIGNAL_DECISION_PLAN_NOTES,
    )
    return DecisionPlanState(
        decision_intent_snapshot=decision_intent_snapshot,
        allowance=allowance,
        plan=plan,
    )


def build_symbol_memory_sections(
    *,
    state: DecisionPlanState,
    cross_horizon: Dict[str, str],
) -> Dict[str, Dict[str, Any]]:
    return {
        "cross_horizon_policy": dict(cross_horizon or {}),
        "intent": dict(state.decision_intent_snapshot or {}),
        "plan": {
            "action": state.plan.action,
            "direction": state.plan.direction,
            "notes": state.plan.notes,
        },
    }


def build_symbol_memory_record_payload(
    *,
    ts: int,
    event_id: str,
    signal_event: Dict[str, Any],
    msl_summary: str,
    signal: Any,
    state: DecisionPlanState,
    cross_horizon: Dict[str, str],
    contract_warnings: list[str],
    execution_result: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    memory_sections = build_symbol_memory_sections(state=state, cross_horizon=cross_horizon)
    return {
        "ts": int(ts),
        "event_id": str(event_id or ""),
        "signal_event": dict(signal_event or {}),
        "msl_summary": str(msl_summary or ""),
        "cross_horizon_policy": dict(memory_sections.get("cross_horizon_policy") or {}),
        "signal": {
            "direction": signal.direction,
            "verdict": signal.verdict,
            "confidence": {"level": signal.confidence.level, "score": signal.confidence.score},
        },
        "intent": dict(memory_sections.get("intent") or {}),
        "plan": dict(memory_sections.get("plan") or {}),
        "contract_warnings": [str(x) for x in list(contract_warnings or []) if str(x).strip()],
        "execution_result": dict(execution_result or {}),
    }


def build_execution_decision_payload(
    *,
    default_decision_id: str,
    default_exchange: str,
    default_symbol: str,
    signal_decision: SignalDecision,
    plan: ExecutionPlan,
    cross_horizon: Dict[str, str],
    prompt_config_source: str = "",
    prompt_config_version: str = "",
    ai_adaptive_enabled: bool = False,
    ai_adaptive_mode: str = "observe",
) -> Dict[str, Any]:
    signal_conf = signal_decision.confidence
    decision_confidence_source = "agent_signal_decision"
    decision_confidence = {
        "level": str(signal_conf.level or "low"),
        "score": float(signal_conf.score or 0.0),
    }
    verdict = str(signal_decision.signal_verdict or "uncertain").strip().lower()
    direction = str(signal_decision.signal_direction or "none").strip().lower()
    agent_action_hint = "add" if verdict == "accept" and direction in {"long", "short"} else "hold"
    payload = {
        "decision_id": str(signal_decision.decision_id or default_decision_id),
        "exchange": str(signal_decision.exchange or default_exchange),
        "symbol": str(signal_decision.symbol or default_symbol),
        "direction_intent": str(signal_decision.signal_direction or "none"),
        "decision_confidence": dict(decision_confidence),
        "cross_horizon_policy": dict(cross_horizon or {}),
        "risk_hints": {
            "agent_action_hint": agent_action_hint,
            "agent_notes": str(plan.notes or ""),
            "decision_confidence": dict(decision_confidence),
            "decision_confidence_source": decision_confidence_source,
            "decision_agent_key": str(signal_decision.decision_agent_key or ""),
            "decision_mode": str(signal_decision.decision_mode or "rule"),
            "llm_parse_status": str(signal_decision.llm_parse_status or ""),
            "prompt_config_source": str(prompt_config_source or ""),
            "prompt_config_version": str(prompt_config_version or ""),
            "signal_verdict": str(signal_decision.signal_verdict or ""),
            "signal_reliability_score": float(signal_decision.reliability_score or 0.0),
            "signal_reasons": list(signal_decision.reasons or []),
        },
    }
    if bool(ai_adaptive_enabled):
        payload["execution_hint"] = {
            "mode": "reserved",
            "adaptive_mode": str(ai_adaptive_mode or "observe"),
            "apply_scope": "none",
        }
        payload["adaptive_profile"] = {}
        payload["adaptive_profile_version"] = "reserved-v0"
        payload["adaptive_explain"] = {"status": "reserved_only"}
    return payload


def build_signal_decision_from_signal(
    *,
    decision_id: str,
    exchange: str,
    symbol: str,
    signal: Any,
    llm_observation: Dict[str, Any],
    decision_agent_key: str,
    decision_mode: str,
    llm_parse_status: str,
) -> SignalDecision:
    verdict = str(getattr(signal, "verdict", "") or "uncertain").strip().lower()
    if verdict not in {"accept", "reject", "uncertain"}:
        verdict = "uncertain"
    direction = str(getattr(signal, "direction", "") or "none").strip().lower()
    if direction not in {"long", "short", "none"}:
        direction = "none"
    mode = str(decision_mode or "rule").strip().lower()
    if mode not in {"llm", "rule_fallback", "rule"}:
        mode = "rule"
    parse_status = str(llm_parse_status or "rule_only").strip().lower()
    if parse_status not in {"llm_ok", "llm_invalid_payload", "llm_status_not_ok", "llm_not_provided", "rule_only"}:
        parse_status = "rule_only"
    conf = getattr(signal, "confidence", None)
    raw_score = float(getattr(conf, "score", 0.0) or 0.0)
    reliability_score = max(0.0, min(1.0, raw_score))
    reasons = [str(x) for x in list(getattr(signal, "invalidation_reasons", []) or []) if str(x)]
    normalized_conf = Confidence(level="low", score=0.0) if conf is None else conf
    return SignalDecision(
        decision_id=str(decision_id or ""),
        exchange=str(exchange or ""),
        symbol=str(symbol or ""),
        decision_agent_key=str(decision_agent_key or "generic"),
        decision_mode=mode,  # type: ignore[arg-type]
        llm_parse_status=parse_status,  # type: ignore[arg-type]
        signal_direction=direction,  # type: ignore[arg-type]
        signal_verdict=verdict,  # type: ignore[arg-type]
        confidence=normalized_conf,  # type: ignore[arg-type]
        reliability_score=reliability_score,
        reasons=reasons,
        evidence_refs=[],
        llm_observation=dict(llm_observation or {}),
    )


def build_workflow_bridge_payload(
    *,
    state: DecisionPlanState,
    signal_decision: SignalDecision,
    pipeline_mode: str = "minimal",
) -> Dict[str, Any]:
    _ = pipeline_mode
    mode = "minimal"
    return {
        "pipeline_mode": mode,
        "notes": str(state.plan.notes or ""),
        "decision": {
            "decision_agent_key": signal_decision.decision_agent_key,
            "decision_mode": signal_decision.decision_mode,
            "llm_parse_status": signal_decision.llm_parse_status,
            "signal_verdict": signal_decision.signal_verdict,
            "signal_direction": signal_decision.signal_direction,
            "reliability_score": signal_decision.reliability_score,
        },
        "execution_plan": {
            "action": state.plan.action,
            "direction": state.plan.direction,
            "confidence": {
                "level": state.plan.confidence.level,
                "score": state.plan.confidence.score,
            },
            "notes": state.plan.notes,
        },
    }


def build_recorder_stage_payloads(
    *,
    state: DecisionPlanState,
    signal_decision: SignalDecision,
    pipeline_mode: str,
    cross_horizon: Dict[str, str],
    decision_trace_payload: Dict[str, Any] | None = None,
) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    _ = (pipeline_mode, cross_horizon)
    mode = "minimal"
    out["workflow_bridge"] = build_workflow_bridge_payload(
        state=state,
        signal_decision=signal_decision,
        pipeline_mode=mode,
    )
    if isinstance(decision_trace_payload, dict):
        out["decision_trace"] = dict(decision_trace_payload)
    return out


def build_decision_trace_payload(
    *,
    event_id: str,
    exchange: str,
    symbol: str,
    ts: int,
    signal_event: Dict[str, Any],
    msl: Dict[str, Any],
    key_market_features: Dict[str, Any],
    signal: Any,
    signal_decision: SignalDecision,
    pipeline_mode: str,
    llm_contract_error_code: str,
    llm_contract_errors: list[str],
    router_config_source: str,
    router_config_version: str,
    prompt_config_source: str,
    prompt_config_version: str,
    event_type_diag: Dict[str, Any],
    state: DecisionPlanState,
    llm_observation: Dict[str, Any],
) -> Dict[str, Any]:
    contract_warnings = [str(x) for x in list((key_market_features or {}).get("contract_warnings") or []) if x]
    trace = DecisionTrace(
        event_id=event_id,
        exchange=exchange,
        symbol=symbol,
        ts=ts,
        event=dict(signal_event or {}),
        msl=dict(msl or {}),
        key_features=dict(key_market_features or {}),
        evidence=dict((key_market_features or {}).get("evidence") or {}),
        anomalies=dict((key_market_features or {}).get("anomalies") or {}),
        signal_verdict={
            "direction": signal.direction,
            "verdict": signal.verdict,
            "confidence": {"level": signal.confidence.level, "score": signal.confidence.score},
            "invalidation_reasons": list(signal.invalidation_reasons),
        },
        routing={
            "pipeline_mode": "minimal",
            "decision_agent_key": signal_decision.decision_agent_key,
            "decision_mode": signal_decision.decision_mode,
            "llm_parse_status": signal_decision.llm_parse_status,
            "llm_contract_error_code": str(llm_contract_error_code or ""),
            "llm_contract_errors": list(llm_contract_errors or []),
            "router_config_source": str(router_config_source or ""),
            "router_config_version": str(router_config_version or ""),
            "prompt_config_source": str(prompt_config_source or ""),
            "prompt_config_version": str(prompt_config_version or ""),
            "event_type_raw": str((event_type_diag or {}).get("raw_event_type") or ""),
            "event_type_normalized": str((event_type_diag or {}).get("normalized_event_type") or ""),
            "event_type_match_mode": str((event_type_diag or {}).get("matched") or "empty"),
        },
        execution_plan={
            "action": state.plan.action,
            "direction": state.plan.direction,
            "sizing": dict(state.plan.sizing or {}),
            "notes": state.plan.notes,
        },
        llm_observation=dict(llm_observation or {}),
        memory_metrics=dict((key_market_features or {}).get("memory_observability") or {}),
        contract_warnings=contract_warnings,
        alert_codes=map_alert_codes_from_contract_warnings(contract_warnings),
        tags=["decision_trace"],
    )
    return trace.to_dict()
