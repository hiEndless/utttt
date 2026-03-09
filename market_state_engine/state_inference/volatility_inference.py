from __future__ import annotations

from typing import Any, Dict

from market_state_engine.factors.volatility import infer_expansion_risk, infer_volatility_direction, infer_volatility_state

from .base import InferenceResult
from .views import build_views, safe_dict, safe_text


class VolatilityInferencePlugin:
    name = "volatility_inference"
    order = 30

    def infer(self, *, features: Any, context: Dict[str, Any]) -> InferenceResult:
        direction_bias = str(context.get("direction_bias") or "unknown")
        participant_behavior = str(context.get("participant_behavior") or "unknown")
        v = build_views(features)
        mid = v["mid"]
        mid_mb = v["mid_mb"]
        volatility_state = infer_volatility_state(
            safe_text(mid_mb.get("volatility_state")),
            safe_text(safe_dict(mid.get("participant_background")).get("stability")),
        )
        return InferenceResult(
            partial_state={
                "volatility_state": volatility_state,
                "expansion_risk": infer_expansion_risk(volatility_state, participant_behavior),
                "volatility_direction": infer_volatility_direction(direction_bias),
            }
        )
