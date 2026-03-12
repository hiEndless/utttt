from __future__ import annotations

from typing import Any, Dict

from services.market_state_engine.src.factors.positioning import infer_crowding, infer_oi_trend, infer_participant_behavior

from .base import InferenceResult
from .views import build_views, safe_dict, safe_text


class PositioningInferencePlugin:
    name = "positioning_inference"
    order = 30

    def infer(self, *, features: Any, context: Dict[str, Any]) -> InferenceResult:
        direction_bias = str(context.get("direction_bias") or "unknown")
        v = build_views(features)
        mid = v["mid"]
        crowding_raw = safe_text(safe_dict(mid.get("participant_background")).get("crowding"))
        if crowding_raw in ("high", "low", "insufficient_evidence"):
            crowding_out = crowding_raw
        elif crowding_raw:
            crowding_out = "normal"
        else:
            crowding_out = "unknown"

        oi = safe_dict(features.open_interest)
        d_pct = float(oi.get("delta_oi_pct") or 0.0)
        participant_behavior = infer_participant_behavior(d_pct, safe_text(oi.get("oi_velocity")))
        return InferenceResult(
            partial_state={
                "crowding_out": crowding_out,
                "participant_behavior": participant_behavior,
                "oi_trend": infer_oi_trend(safe_text(oi.get("oi_trend"))),
                "crowding": infer_crowding(crowding_out, direction_bias),
            }
        )
