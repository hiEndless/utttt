from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class SignalAgentSpec:
    key: str
    description: str
    prompt_focus: str
    prompt_checklist: Tuple[str, ...]
    prompt_avoid: Tuple[str, ...]
    prompt_model_id: str = ""


_DEFAULT_AGENT_KEY = "generic"
_SIGNAL_AGENT_REGISTRY: Dict[str, SignalAgentSpec] = {
    "technical": SignalAgentSpec(
        key="technical",
        description="市场指标/技术信号判定",
        prompt_focus="technical_signal_validation",
        prompt_checklist=("trend_structure", "orderbook_liquidity", "oi_change_consistency"),
        prompt_avoid=("news_sentiment_overweight", "execution_action", "risk_gate_decision"),
    ),
    "liquidation": SignalAgentSpec(
        key="liquidation",
        description="大额清算/流动性冲击判定",
        prompt_focus="liquidation_shock_validation",
        prompt_checklist=("liquidation_cluster_strength", "cascade_risk", "rebound_probability"),
        prompt_avoid=("long_horizon_macro_overweight", "execution_action", "risk_gate_decision"),
    ),
    "onchain": SignalAgentSpec(
        key="onchain",
        description="链上钱包/资金流异动判定",
        prompt_focus="onchain_flow_validation",
        prompt_checklist=("wallet_flow_direction", "exchange_inflow_outflow_shift", "source_reliability"),
        prompt_avoid=("micro_orderbook_overweight", "execution_action", "risk_gate_decision"),
    ),
    "social_news": SignalAgentSpec(
        key="social_news",
        description="社媒/新闻/宏观事件判定",
        prompt_focus="social_news_event_validation",
        prompt_checklist=("source_credibility", "cross_source_consistency", "timeliness_and_decay"),
        prompt_avoid=("single_post_overweight", "execution_action", "risk_gate_decision"),
    ),
    "generic": SignalAgentSpec(
        key="generic",
        description="未知类型回退判定",
        prompt_focus="generic_signal_validation",
        prompt_checklist=("direction_consistency", "evidence_quality", "market_regime_fit"),
        prompt_avoid=("position_sizing", "execution_action", "risk_gate_decision"),
    ),
}


def list_signal_agent_keys() -> Tuple[str, ...]:
    return tuple(_SIGNAL_AGENT_REGISTRY.keys())


def signal_agent_key_set() -> set[str]:
    return set(list_signal_agent_keys())


def resolve_signal_agent_key(value: str | None) -> str:
    key = str(value or "").strip().lower()
    return key if key in _SIGNAL_AGENT_REGISTRY else _DEFAULT_AGENT_KEY


def get_signal_agent_spec(value: str | None) -> SignalAgentSpec:
    key = resolve_signal_agent_key(value)
    return _SIGNAL_AGENT_REGISTRY[key]


def default_signal_decision_prompt_profiles() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for key in list_signal_agent_keys():
        spec = get_signal_agent_spec(key)
        row: Dict[str, Any] = {
            "focus": spec.prompt_focus,
            "checklist": list(spec.prompt_checklist),
            "avoid": list(spec.prompt_avoid),
        }
        if spec.prompt_model_id:
            row["model_id"] = spec.prompt_model_id
        out[key] = row
    return out
