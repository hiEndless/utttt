from __future__ import annotations

from typing import Any, Dict

from market_state_engine.factors.regime import infer_direction_bias, infer_horizon_alignment, infer_regime, normalize_trend_strength

from .base import InferenceResult
from .views import build_views, safe_dict, safe_text


class RuleRegimeInferencePlugin:
    name = "regime_inference"
    order = 10

    def infer(self, *, features: Any, context: Dict[str, Any]) -> InferenceResult:
        _ = context
        v = build_views(features)
        mid_tm = v["mid_tm"]
        short_tm = v["short_tm"]
        mid_mb = v["mid_mb"]
        short_mb = v["short_mb"]

        direction_bias = infer_direction_bias(safe_text(mid_tm.get("price_direction")))
        trend_strength = normalize_trend_strength(safe_text(mid_tm.get("price_strength")))
        horizon_alignment = infer_horizon_alignment(
            safe_text(short_tm.get("price_direction")),
            safe_text(mid_tm.get("price_direction")),
            safe_text(short_tm.get("price_strength")),
            safe_text(mid_tm.get("price_strength")),
        )
        regime = infer_regime(
            safe_text(safe_dict(short_mb.get("trend_context") or {}).get("label")),
            safe_text(safe_dict(mid_mb.get("trend_context") or {}).get("label")),
            horizon_alignment,
        )
        return InferenceResult(
            partial_state={
                "direction_bias": direction_bias,
                "trend_strength": trend_strength,
                "horizon_alignment": horizon_alignment,
                "regime": regime,
            }
        )
