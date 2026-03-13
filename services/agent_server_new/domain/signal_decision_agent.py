from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Protocol

from services.market_state_engine.src.contracts import MarketStateMSL

from services.agent_server_new.domain.contracts import SignalVerdict
from services.agent_server_new.domain.signal_router import route_signal_agent_key
from services.agent_server_new.experts.signal_evaluator import ExpertContext, evaluate_signal


@dataclass(frozen=True)
class SignalDecisionEvalResult:
    """信号主判结果：保留规则/模型判定 + 路由到的决策 agent key。"""

    signal: SignalVerdict
    decision_agent_key: str


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
    ) -> SignalDecisionEvalResult:
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
        )
