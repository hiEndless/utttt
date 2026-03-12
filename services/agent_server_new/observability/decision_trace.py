from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class DecisionTrace:
    """决策追踪：用于调试、回放与 explainable AI 的数据载体。"""

    event_id: str
    exchange: str
    symbol: str
    ts: int

    event: Dict[str, Any]
    msl: Dict[str, Any]
    key_features: Dict[str, Any]
    evidence: Dict[str, Any]
    anomalies: Dict[str, Any]

    signal_verdict: Dict[str, Any]
    intent: Dict[str, Any]
    rule_plan: Dict[str, Any]
    strategy_gate_result: Dict[str, Any]
    risk_gate: Dict[str, Any]
    execution_plan: Dict[str, Any]
    memory_metrics: Dict[str, Any] = field(default_factory=dict)
    contract_warnings: List[str] = field(default_factory=list)

    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "ts": self.ts,
            "event": dict(self.event),
            "msl": dict(self.msl),
            "key_features": dict(self.key_features),
            "evidence": dict(self.evidence),
            "anomalies": dict(self.anomalies),
            "signal_verdict": dict(self.signal_verdict),
            "intent": dict(self.intent),
            "rule_plan": dict(self.rule_plan),
            "strategy_gate_result": dict(self.strategy_gate_result),
            "risk_gate": dict(self.risk_gate),
            "execution_plan": dict(self.execution_plan),
            "memory_metrics": dict(self.memory_metrics),
            "contract_warnings": [str(x) for x in list(self.contract_warnings or []) if x],
            "tags": list(self.tags),
        }
