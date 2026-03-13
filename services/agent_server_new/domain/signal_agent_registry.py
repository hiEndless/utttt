from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class SignalAgentSpec:
    key: str
    description: str


_DEFAULT_AGENT_KEY = "generic"
_SIGNAL_AGENT_REGISTRY: Dict[str, SignalAgentSpec] = {
    "technical": SignalAgentSpec(key="technical", description="市场指标/技术信号判定"),
    "liquidation": SignalAgentSpec(key="liquidation", description="大额清算/流动性冲击判定"),
    "onchain": SignalAgentSpec(key="onchain", description="链上钱包/资金流异动判定"),
    "social_news": SignalAgentSpec(key="social_news", description="社媒/新闻/宏观事件判定"),
    "generic": SignalAgentSpec(key="generic", description="未知类型回退判定"),
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
