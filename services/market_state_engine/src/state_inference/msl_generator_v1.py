from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Dict, List

from services.market_state_engine.src.contracts import KeyLevels, LiquidityState, MarketRegime, MarketStateMSL, PositioningState, RiskState, StructureState, VolatilityState

if TYPE_CHECKING:
    from services.market_state_engine.src.engine import MarketStateFeatures


def _iso_utc_from_ms(ms: int) -> str:
    try:
        dt = datetime.datetime.fromtimestamp(float(ms) / 1000.0, tz=datetime.timezone.utc).replace(microsecond=0)
    except Exception:
        dt = datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")


def _build_summary_v1(state: Dict[str, Any]) -> str:
    parts: List[str] = []
    trend = str(state.get("trend") or "unknown")
    phase = str(state.get("phase") or "unknown")
    dominant_pressure = str(state.get("dominant_pressure") or "unknown")
    oi_trend = str(state.get("oi_trend") or "unknown")
    liquidity_risk = str(state.get("liquidity_risk") or "unknown")
    volatility_state = str(state.get("volatility_state") or "unknown")

    if trend in ("bullish", "bearish", "sideways"):
        parts.append(f"{trend} {phase}".strip())
    if dominant_pressure in ("buyers", "sellers", "balanced"):
        parts.append(f"{dominant_pressure} pressure")
    if oi_trend in ("expanding", "contracting", "flat"):
        parts.append(f"OI {oi_trend}")
    if liquidity_risk in ("short_squeeze", "long_squeeze"):
        parts.append(f"{liquidity_risk} risk")
    if volatility_state in ("low", "normal", "high"):
        parts.append(f"volatility {volatility_state}")

    summary = ". ".join([p for p in parts if p]).strip()
    if summary:
        summary = summary + "."
    return summary


def build_msl_v1(*, features: "MarketStateFeatures", state: Dict[str, Any], plugin_evidence: Dict[str, Any], warnings: List[str]) -> MarketStateMSL:
    anomaly_flags = [str(x) for x in list(state.get("anomaly_flags") or []) if x]
    summary = _build_summary_v1(state)

    return MarketStateMSL(
        version=2,
        timestamp=_iso_utc_from_ms(int(features.ts)),
        symbol=features.symbol,
        market_regime=MarketRegime(
            trend=str(state.get("trend") or "unknown"),
            phase=str(state.get("phase") or "unknown"),
            timeframe_alignment=str(state.get("timeframe_alignment") or "unknown"),
            strength=float(state.get("strength") or 0.0),
        ),
        liquidity=LiquidityState(
            dominant_pressure=str(state.get("dominant_pressure") or "unknown"),
            liquidity_risk=str(state.get("liquidity_risk") or "unknown"),
            orderbook_bias=str(state.get("orderbook_bias") or "unknown"),
            liquidation_proximity=str(state.get("liquidation_proximity") or "unknown"),
        ),
        positioning=PositioningState(
            crowding=str(state.get("crowding") or "unknown"),
            whale_bias="unknown",
            retail_bias="unknown",
            oi_trend=str(state.get("oi_trend") or "unknown"),
        ),
        volatility=VolatilityState(
            volatility_regime=str(state.get("volatility_state") or "unknown"),
            expansion_risk=str(state.get("expansion_risk") or "unknown"),
            volatility_direction=str(state.get("volatility_direction") or "unknown"),
        ),
        risk=RiskState(
            cascade_risk=str(state.get("cascade_risk") or "unknown"),
            squeeze_probability=str(state.get("squeeze_probability") or "unknown"),
            reversal_risk=str(state.get("reversal_risk") or "unknown"),
        ),
        market_structure=StructureState(
            support_strength="unknown",
            resistance_strength="unknown",
            range_state=str(state.get("range_state") or "unknown"),
            trend_structure=str(state.get("trend_structure") or "unknown"),
        ),
        key_levels=KeyLevels(),
        anomalies=sorted(set([str(x) for x in list(anomaly_flags or []) if x])),
        summary=summary,
        evidence={
            "exchange": features.exchange,
            "evidence": dict(features.evidence),
            "anomalies": dict(features.anomalies),
            "features": {
                "orderbook": dict(features.orderbook),
                "open_interest": dict(features.open_interest),
                "horizons": dict(features.horizons),
            },
            "plugin_evidence": dict(plugin_evidence),
            "plugin_warnings": [str(x) for x in list(warnings or []) if x],
        },
    )

