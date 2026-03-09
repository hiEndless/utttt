from __future__ import annotations

from typing import Any, Dict

from market_state_engine.factors.regime import infer_market_phase, infer_phase, infer_strength, infer_timeframe_alignment, infer_trend
from market_state_engine.factors.risk import (
    build_risk_flags,
    infer_cascade_risk,
    infer_market_fragility,
    infer_reversal_risk,
    infer_squeeze_probability,
)

from .base import InferenceResult
from .views import safe_dict, safe_list


class RiskInferencePlugin:
    name = "risk_inference"
    order = 50

    def infer(self, *, features: Any, context: Dict[str, Any]) -> InferenceResult:
        direction_bias = str(context.get("direction_bias") or "unknown")
        trend_strength = str(context.get("trend_strength") or "unknown")
        horizon_alignment = str(context.get("horizon_alignment") or "unknown")
        regime = str(context.get("regime") or "unknown")
        crowding_out = str(context.get("crowding_out") or "unknown")
        participant_behavior = str(context.get("participant_behavior") or "unknown")
        volatility_state = str(context.get("volatility_state") or "unknown")
        liquidity_state = str(context.get("liquidity_state") or "unknown")
        liquidity_risk = str(context.get("liquidity_risk") or "unknown")

        anomaly_flags = [str(x) for x in safe_list(safe_dict(features.anomalies).get("flags")) if x]
        oi_flags = [str(x) for x in safe_list(safe_dict(features.open_interest).get("risk_flags")) if x]
        risk_flags = build_risk_flags(
            liquidity_state=liquidity_state,
            crowding_out=crowding_out,
            oi_flags=oi_flags,
        )

        market_fragility = infer_market_fragility(
            anomaly_flags=anomaly_flags,
            liquidity_state=liquidity_state,
            volatility_state=volatility_state,
            crowding_out=crowding_out,
        )
        market_phase = infer_market_phase(
            regime=regime,
            participant_behavior=participant_behavior,
            crowding_out=crowding_out,
            volatility_state=volatility_state,
        )
        phase = infer_phase(market_phase)

        return InferenceResult(
            partial_state={
                "anomaly_flags": anomaly_flags,
                "risk_flags": risk_flags,
                "market_fragility": market_fragility,
                "market_phase": market_phase,
                "trend": infer_trend(direction_bias),
                "phase": phase,
                "timeframe_alignment": infer_timeframe_alignment(horizon_alignment),
                "strength": infer_strength(trend_strength, horizon_alignment, market_fragility),
                "cascade_risk": infer_cascade_risk(market_fragility),
                "squeeze_probability": infer_squeeze_probability(
                    liquidity_risk=liquidity_risk,
                    anomaly_flags=anomaly_flags,
                    crowding_out=crowding_out,
                    volatility_state=volatility_state,
                ),
                "reversal_risk": infer_reversal_risk(
                    horizon_alignment=horizon_alignment,
                    phase=phase,
                    volatility_state=volatility_state,
                ),
            }
        )
