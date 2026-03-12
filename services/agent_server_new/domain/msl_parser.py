from __future__ import annotations

from typing import Any, Dict

from services.market_state_engine.src.contracts import (
    KeyLevels,
    LiquidityState,
    MarketRegime,
    MarketStateMSL,
    PositioningState,
    RiskState,
    StructureState,
    VolatilityState,
)


def _build_msl_from_dict(d: Dict[str, Any]) -> MarketStateMSL:
    mr = d.get("market_regime") or {}
    ls = d.get("liquidity_state") or {}
    ps = d.get("positioning_state") or {}
    vs = d.get("volatility_state") or {}
    # Prefer canonical market_risk_state; keep legacy risk_state as compatibility fallback.
    rs = d.get("market_risk_state") or d.get("risk_state") or {}
    st = d.get("market_structure_state") or {}
    kl = d.get("key_levels") or {}
    return MarketStateMSL(
        version=int(d.get("version") or 1),
        timestamp=str(d.get("timestamp") or ""),
        symbol=str(d.get("symbol") or ""),
        market_regime=MarketRegime(
            trend=str(mr.get("trend") or "unknown"),  # type: ignore[arg-type]
            phase=str(mr.get("phase") or "unknown"),  # type: ignore[arg-type]
            timeframe_alignment=str(mr.get("timeframe_alignment") or "unknown"),  # type: ignore[arg-type]
            strength=float(mr.get("strength") or 0.0),
        ),
        liquidity=LiquidityState(
            dominant_pressure=str(ls.get("dominant_pressure") or "unknown"),  # type: ignore[arg-type]
            liquidity_risk=str(ls.get("liquidity_risk") or "unknown"),  # type: ignore[arg-type]
            orderbook_bias=str(ls.get("orderbook_bias") or "unknown"),  # type: ignore[arg-type]
            liquidation_proximity=str(ls.get("liquidation_proximity") or "unknown"),  # type: ignore[arg-type]
        ),
        positioning=PositioningState(
            crowding=str(ps.get("crowding") or "unknown"),  # type: ignore[arg-type]
            whale_bias=str(ps.get("whale_bias") or "unknown"),  # type: ignore[arg-type]
            retail_bias=str(ps.get("retail_bias") or "unknown"),  # type: ignore[arg-type]
            oi_trend=str(ps.get("oi_trend") or "unknown"),  # type: ignore[arg-type]
        ),
        volatility=VolatilityState(
            volatility_regime=str(vs.get("volatility_regime") or "unknown"),  # type: ignore[arg-type]
            expansion_risk=str(vs.get("expansion_risk") or "unknown"),  # type: ignore[arg-type]
            volatility_direction=str(vs.get("volatility_direction") or "unknown"),  # type: ignore[arg-type]
        ),
        risk=RiskState(
            cascade_risk=str(rs.get("cascade_risk") or "unknown"),  # type: ignore[arg-type]
            squeeze_probability=str(rs.get("squeeze_probability") or "unknown"),  # type: ignore[arg-type]
            reversal_risk=str(rs.get("reversal_risk") or "unknown"),  # type: ignore[arg-type]
        ),
        market_structure=StructureState(
            support_strength=str(st.get("support_strength") or "unknown"),  # type: ignore[arg-type]
            resistance_strength=str(st.get("resistance_strength") or "unknown"),  # type: ignore[arg-type]
            range_state=str(st.get("range_state") or "unknown"),  # type: ignore[arg-type]
            trend_structure=str(st.get("trend_structure") or "unknown"),  # type: ignore[arg-type]
        ),
        key_levels=KeyLevels(
            major_support=[float(x) for x in list(kl.get("major_support") or []) if x is not None],
            major_resistance=[float(x) for x in list(kl.get("major_resistance") or []) if x is not None],
            liquidation_clusters=[float(x) for x in list(kl.get("liquidation_clusters") or []) if x is not None],
        ),
        anomalies=[str(x) for x in list(d.get("anomalies") or []) if x],
        summary=str(d.get("summary") or ""),
        evidence=dict(d.get("evidence") or {}),
    )
