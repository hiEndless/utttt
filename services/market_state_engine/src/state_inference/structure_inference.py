from __future__ import annotations

from typing import Any, Dict

from services.market_state_engine.src.factors.structure import infer_range_state, infer_trend_structure

from .base import InferenceResult


class StructureInferencePlugin:
    name = "structure_inference"
    order = 60

    def infer(self, *, features: Any, context: Dict[str, Any]) -> InferenceResult:
        _ = features
        regime = str(context.get("regime") or "unknown")
        direction_bias = str(context.get("direction_bias") or "unknown")
        return InferenceResult(
            partial_state={
                "range_state": infer_range_state(regime),
                "trend_structure": infer_trend_structure(direction_bias),
            }
        )

