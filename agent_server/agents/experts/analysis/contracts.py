from __future__ import annotations

from typing import List, Literal, Optional, TypedDict


SignalVerdict = Literal["VALID", "WEAK_VALID", "INVALID"]
SignalAlignment = Literal["ALIGNED", "CONFLICT", "STRONGLY_CONFLICT"]
ConfidenceAdjustment = Literal["none", "down"]


class SignalValidationOutput(TypedDict):
    verdict: SignalVerdict
    alignment: SignalAlignment
    confidence_adjustment: ConfidenceAdjustment
    reasoning: List[str]


RiskState = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
RecommendedAction = Literal["ADD_POSITION", "HOLD", "DEFENSIVE", "REDUCE", "EXIT"]


class PositionRiskOutput(TypedDict, total=False):
    verdict: RiskState
    suggestion: RecommendedAction
    reduce_pct: Optional[float]
    add_pct: Optional[float]
    tighten_stop: bool
    freeze_add_position_min: int
    reasoning: List[str]
