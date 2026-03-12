from __future__ import annotations

from typing import Any, Dict

from services.market_state_engine.src.factors.liquidity import (
    infer_dominant_pressure,
    infer_liquidation_proximity,
    infer_liquidity_risk,
    infer_liquidity_state,
    infer_orderbook_bias,
)
from services.market_state_engine.src.factors.risk import build_risk_flags

from .base import InferenceResult
from .views import safe_dict, safe_list, safe_text


class LiquidityInferencePlugin:
    name = "liquidity_inference"
    # 依赖 positioning 插件产出的 crowding_out，因此顺序放后。
    order = 40

    def infer(self, *, features: Any, context: Dict[str, Any]) -> InferenceResult:
        direction_bias = str(context.get("direction_bias") or "unknown")
        crowding_out = str(context.get("crowding_out") or "unknown")
        ob = safe_dict(features.orderbook)
        stability = safe_text(ob.get("stability"))
        liquidity_state = infer_liquidity_state(bool(ob.get("liquidity_vacuum") is True), stability)
        oi_flags = [str(x) for x in safe_list(safe_dict(features.open_interest).get("risk_flags")) if x]
        # 沿用旧逻辑：先按 liquidity+crowding+oi 组合 risk_flags，再推导 squeeze 风险。
        risk_flags = build_risk_flags(
            liquidity_state=liquidity_state,
            crowding_out=crowding_out,
            oi_flags=oi_flags,
        )
        squeeze_flag = "liquidation_cluster" in set(risk_flags)
        liquidity_risk = infer_liquidity_risk(squeeze_flag, direction_bias)
        return InferenceResult(
            partial_state={
                "liquidity_state": liquidity_state,
                "risk_flags": risk_flags,
                "dominant_pressure": infer_dominant_pressure(direction_bias),
                "orderbook_bias": infer_orderbook_bias(stability),
                "liquidity_risk": liquidity_risk,
                "liquidation_proximity": infer_liquidation_proximity(squeeze_flag),
            }
        )
