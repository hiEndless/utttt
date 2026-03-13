from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Protocol

from services.market_state_engine.src.contracts import MarketStateMSL

from services.agent_server_new.domain.contracts import Confidence, SignalVerdict
from services.agent_server_new.domain.signal_router import route_signal_agent_key
from services.agent_server_new.experts.signal_evaluator import ExpertContext, evaluate_signal


@dataclass(frozen=True)
class SignalDecisionEvalResult:
    """信号主判结果：保留规则/模型判定 + 路由到的决策 agent key。"""

    signal: SignalVerdict
    decision_agent_key: str
    decision_mode: Literal["llm", "rule_fallback", "rule"] = "rule"
    llm_parse_status: str = "rule_only"


class SignalDecisionAgent(Protocol):
    def decide(
        self,
        *,
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
        decision_agent_key = route_signal_agent_key(
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
            decision_agent_key=decision_agent_key,
            decision_mode="rule",
            llm_parse_status="rule_only",
        )


class RoutedHybridSignalDecisionAgent(RoutedRuleBasedSignalDecisionAgent):
    """混合实现：优先消费 LLM 判定，解析失败/异常时回落规则判定。"""
    _ALLOWED_LLM_FIELDS = {
        "signal_verdict",
        "signal_direction",
        "reliability_score",
        "confidence_score",
        "score",
        "reasons",
        "evidence_refs",
        "notes",
    }

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

    def _parse_llm_signal(self, llm_result: Dict[str, Any]) -> SignalVerdict | None:
        data = dict(llm_result or {})
        raw = data.get("raw_content")
        if not isinstance(raw, str) or not raw.strip():
            return None
        try:
            parsed = json.loads(raw)
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        if any(str(k) not in self._ALLOWED_LLM_FIELDS for k in parsed.keys()):
            return None

        verdict = str(parsed.get("signal_verdict") or "").strip().lower()
        if verdict not in {"accept", "reject", "uncertain"}:
            return None
        direction = str(parsed.get("signal_direction") or "").strip().lower()
        if direction not in {"long", "short", "none"}:
            return None
        raw_score = parsed.get("reliability_score")
        if raw_score is None:
            raw_score = parsed.get("confidence_score")
        if raw_score is None:
            raw_score = parsed.get("score")
        if raw_score is None:
            return None
        try:
            score = float(raw_score)
        except Exception:
            return None
        if score < 0.0 or score > 1.0:
            return None
        reasons_raw = parsed.get("reasons")
        if reasons_raw is None:
            reasons = []
        elif isinstance(reasons_raw, list):
            reasons = [str(x).strip() for x in reasons_raw if str(x).strip()]
        else:
            return None
        return SignalVerdict(
            direction=direction,  # type: ignore[arg-type]
            verdict=verdict,  # type: ignore[arg-type]
            confidence=Confidence(level=self._score_to_level(score), score=score),
            invalidation_reasons=reasons,
            notes="llm_signal_decision",
        )

    def decide(
        self,
        *,
        signal_direction: str,
        msl: MarketStateMSL,
        key_market_features: Dict[str, Any],
        active_events: List[Dict[str, Any]],
        signal_event: Dict[str, Any],
        position_context: Dict[str, Any],
        llm_result: Dict[str, Any] | None = None,
    ) -> SignalDecisionEvalResult:
        decision_agent_key = self._route_agent_key(signal_event=signal_event)
        llm = dict(llm_result or {})
        if str(llm.get("status") or "").strip().lower() == "ok":
            llm_signal = self._parse_llm_signal(llm)
            if llm_signal is not None:
                return SignalDecisionEvalResult(
                    signal=llm_signal,
                    decision_agent_key=decision_agent_key,
                    decision_mode="llm",
                    llm_parse_status="llm_ok",
                )
            fallback = super().decide(
                signal_direction=signal_direction,
                msl=msl,
                key_market_features=key_market_features,
                active_events=active_events,
                signal_event=signal_event,
                position_context=position_context,
            )
            return SignalDecisionEvalResult(
                signal=fallback.signal,
                decision_agent_key=decision_agent_key,
                decision_mode="rule_fallback",
                llm_parse_status="llm_invalid_payload",
            )
        fallback = super().decide(
            signal_direction=signal_direction,
            msl=msl,
            key_market_features=key_market_features,
            active_events=active_events,
            signal_event=signal_event,
            position_context=position_context,
        )
        return SignalDecisionEvalResult(
            signal=fallback.signal,
            decision_agent_key=decision_agent_key,
            decision_mode="rule",
            llm_parse_status="llm_status_not_ok" if llm else "llm_not_provided",
        )
