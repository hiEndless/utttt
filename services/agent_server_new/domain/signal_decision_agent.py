from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Protocol

from services.market_state_engine.src.contracts import MarketStateMSL

from services.agent_server_new.domain.contracts import Confidence, LLMContractErrorCode, LLMParseStatus, SignalVerdict
from services.agent_server_new.domain.llm_signal_decision_schema_guard import validate_llm_signal_decision_payload
from services.agent_server_new.domain.signal_router import route_signal_agent_key
from services.agent_server_new.experts.signal_evaluator import ExpertContext, evaluate_signal


@dataclass(frozen=True)
class SignalDecisionEvalResult:
    """信号主判结果：保留规则/模型判定 + 路由到的决策 agent key。"""

    signal: SignalVerdict
    decision_agent_key: str
    decision_mode: Literal["llm", "rule_fallback", "rule"] = "rule"
    llm_parse_status: LLMParseStatus = "rule_only"
    llm_contract_error_code: LLMContractErrorCode = ""
    llm_contract_errors: List[str] = field(default_factory=list)


class SignalDecisionAgent(Protocol):
    def decide(
        self,
        *,
        decision_agent_key: str | None = None,
        signal_direction: str,
        msl: MarketStateMSL,
        key_market_features: Dict[str, Any],
        active_events: List[Dict[str, Any]],
        signal_event: Dict[str, Any],
        position_context: Dict[str, Any],
        llm_result: Dict[str, Any] | None = None,
    ) -> SignalDecisionEvalResult:
        """执行信号判定并给出 agent 路由键。"""


class RoutedRuleBasedSignalDecisionAgent:
    """默认实现：先路由，再执行规则判定（兼容阶段）。"""

    def __init__(
        self,
        *,
        router_config: Dict[str, Any] | None = None,
        signal_evaluator: Callable[..., SignalVerdict] = evaluate_signal,
    ) -> None:
        self._router_config = dict(router_config or {})
        self._signal_evaluator = signal_evaluator

    def decide(
        self,
        *,
        decision_agent_key: str | None = None,
        signal_direction: str,
        msl: MarketStateMSL,
        key_market_features: Dict[str, Any],
        active_events: List[Dict[str, Any]],
        signal_event: Dict[str, Any],
        position_context: Dict[str, Any],
        llm_result: Dict[str, Any] | None = None,
    ) -> SignalDecisionEvalResult:
        _ = llm_result
        raw_signal_event = dict(signal_event or {})
        signal_payload = dict(raw_signal_event.get("payload") or raw_signal_event)
        routed_agent_key = str(decision_agent_key or "").strip().lower() or route_signal_agent_key(
            signal_event={"payload": signal_payload},
            router_config=self._router_config,
        )
        signal = self._signal_evaluator(
            ctx=ExpertContext(
                msl=msl,
                key_market_features=dict(key_market_features or {}),
                active_events=list(active_events or []),
                signal_event=dict(signal_event or {}),
                position_context=dict(position_context or {}),
            ),
            signal_direction=signal_direction,
        )
        return SignalDecisionEvalResult(
            signal=signal,
            decision_agent_key=routed_agent_key,
            decision_mode="rule",
            llm_parse_status="rule_only",
            llm_contract_error_code="",
            llm_contract_errors=[],
        )


class RoutedHybridSignalDecisionAgent(RoutedRuleBasedSignalDecisionAgent):
    """混合实现：优先消费 LLM 判定，解析失败/异常时回落规则判定。"""

    def _route_agent_key(self, *, signal_event: Dict[str, Any]) -> str:
        raw_signal_event = dict(signal_event or {})
        signal_payload = dict(raw_signal_event.get("payload") or raw_signal_event)
        return route_signal_agent_key(
            signal_event={"payload": signal_payload},
            router_config=self._router_config,
        )

    def _score_to_level(self, score: float) -> Literal["high", "medium", "low"]:
        if score >= 0.75:
            return "high"
        if score >= 0.55:
            return "medium"
        return "low"

    def _parse_llm_signal(self, llm_result: Dict[str, Any]) -> tuple[SignalVerdict | None, str, List[str]]:
        data = dict(llm_result or {})
        raw = data.get("raw_content")
        if not isinstance(raw, str) or not raw.strip():
            return None, "llm_raw_content_missing", ["missing raw_content"]
        try:
            parsed = json.loads(raw)
        except Exception:
            return None, "llm_json_parse_error", ["raw_content is not valid json"]
        if not isinstance(parsed, dict):
            return None, "llm_json_not_object", ["raw_content must be a json object"]
        ok, errors = validate_llm_signal_decision_payload(parsed)
        if not ok:
            return None, "llm_schema_validation_failed", list(errors[:8])
        verdict = str(parsed.get("signal_verdict") or "").strip().lower()
        direction = str(parsed.get("signal_direction") or "").strip().lower()
        raw_score = parsed.get("confidence_score")
        try:
            score = float(raw_score)
        except Exception:
            return None, "llm_confidence_parse_error", ["confidence_score parse failed"]
        reasons_raw = parsed.get("reasons")
        reasons = [str(x).strip() for x in list(reasons_raw or []) if str(x).strip()]
        return (
            SignalVerdict(
                direction=direction,  # type: ignore[arg-type]
                verdict=verdict,  # type: ignore[arg-type]
                confidence=Confidence(level=self._score_to_level(score), score=score),
                invalidation_reasons=reasons,
                notes="llm_signal_decision",
            ),
            "",
            [],
        )

    def decide(
        self,
        *,
        decision_agent_key: str | None = None,
        signal_direction: str,
        msl: MarketStateMSL,
        key_market_features: Dict[str, Any],
        active_events: List[Dict[str, Any]],
        signal_event: Dict[str, Any],
        position_context: Dict[str, Any],
        llm_result: Dict[str, Any] | None = None,
    ) -> SignalDecisionEvalResult:
        routed_agent_key = str(decision_agent_key or "").strip().lower() or self._route_agent_key(signal_event=signal_event)
        llm = dict(llm_result or {})
        if str(llm.get("status") or "").strip().lower() == "ok":
            llm_signal, err_code, err_list = self._parse_llm_signal(llm)
            if llm_signal is not None:
                return SignalDecisionEvalResult(
                    signal=llm_signal,
                    decision_agent_key=routed_agent_key,
                    decision_mode="llm",
                    llm_parse_status="llm_ok",
                    llm_contract_error_code="",
                    llm_contract_errors=[],
                )
            fallback = super().decide(
                decision_agent_key=routed_agent_key,
                signal_direction=signal_direction,
                msl=msl,
                key_market_features=key_market_features,
                active_events=active_events,
                signal_event=signal_event,
                position_context=position_context,
            )
            return SignalDecisionEvalResult(
                signal=fallback.signal,
                decision_agent_key=routed_agent_key,
                decision_mode="rule_fallback",
                llm_parse_status="llm_invalid_payload",
                llm_contract_error_code=str(err_code or "llm_schema_validation_failed"),
                llm_contract_errors=list(err_list or []),
            )
        fallback = super().decide(
            decision_agent_key=routed_agent_key,
            signal_direction=signal_direction,
            msl=msl,
            key_market_features=key_market_features,
            active_events=active_events,
            signal_event=signal_event,
            position_context=position_context,
        )
        return SignalDecisionEvalResult(
            signal=fallback.signal,
            decision_agent_key=routed_agent_key,
            decision_mode="rule",
            llm_parse_status="llm_status_not_ok" if llm else "llm_not_provided",
            llm_contract_error_code="",
            llm_contract_errors=[],
        )
