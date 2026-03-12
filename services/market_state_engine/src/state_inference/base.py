from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol


@dataclass(frozen=True)
class InferenceResult:
    partial_state: Dict[str, Any] = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


class StateInferencePlugin(Protocol):
    name: str
    order: int

    def infer(self, *, features: Any, context: Dict[str, Any]) -> InferenceResult:
        ...
