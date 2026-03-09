from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, List

from market_state_engine.contracts import KeyLevels, LiquidityState, MarketRegime, MarketStateMSL, PositioningState, RiskState, StructureState, VolatilityState

if TYPE_CHECKING:
    from market_state_engine.engine import MarketStateFeatures

from .common import safe_dict, safe_list, safe_text
from .liquidity import (
    infer_dominant_pressure,
    infer_liquidation_proximity,
    infer_liquidity_risk,
    infer_liquidity_state,
    infer_orderbook_bias,
)
from .positioning import infer_crowding, infer_oi_trend, infer_participant_behavior
from .regime import (
    infer_direction_bias,
    infer_horizon_alignment,
    infer_market_phase,
    infer_phase,
    infer_regime,
    infer_strength,
    infer_timeframe_alignment,
    infer_trend,
    normalize_trend_strength,
)
from .risk import build_risk_flags, infer_cascade_risk, infer_market_fragility, infer_reversal_risk, infer_squeeze_probability
from .structure import infer_range_state, infer_trend_structure
from .volatility import infer_expansion_risk, infer_volatility_direction, infer_volatility_state


def _iso_utc_from_ms(ms: int) -> str:
    try:
        dt = datetime.datetime.fromtimestamp(float(ms) / 1000.0, tz=datetime.timezone.utc).replace(microsecond=0)
    except Exception:
        dt = datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")


def build_msl_from_features(features: MarketStateFeatures) -> MarketStateMSL:
    mid = safe_dict(features.horizons.get("mid_term"))
    short = safe_dict(features.horizons.get("short_term"))

    mid_mb = safe_dict(mid.get("market_background"))
    short_mb = safe_dict(short.get("market_background"))
    mid_tm = safe_dict(mid_mb.get("trend_memory"))
    short_tm = safe_dict(short_mb.get("trend_memory"))

    direction_bias = infer_direction_bias(safe_text(mid_tm.get("price_direction")))
    trend_strength = normalize_trend_strength(safe_text(mid_tm.get("price_strength")))

    volatility_state = infer_volatility_state(
        safe_text(mid_mb.get("volatility_state")),
        safe_text(safe_dict(mid.get("participant_background")).get("stability")),
    )

    crowding_raw = safe_text(safe_dict(mid.get("participant_background")).get("crowding"))
    if crowding_raw in ("high", "low", "insufficient_evidence"):
        crowding_out = crowding_raw
    elif crowding_raw:
        crowding_out = "normal"
    else:
        crowding_out = "unknown"

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

    d_pct = float(safe_dict(features.open_interest).get("delta_oi_pct") or 0.0)
    participant_behavior = infer_participant_behavior(d_pct, safe_text(safe_dict(features.open_interest).get("oi_velocity")))

    anomaly_flags = [str(x) for x in safe_list(safe_dict(features.anomalies).get("flags")) if x]
    liquidity_state = infer_liquidity_state(
        bool(safe_dict(features.orderbook).get("liquidity_vacuum") is True),
        safe_text(safe_dict(features.orderbook).get("stability")),
    )
    oi_flags = [str(x) for x in safe_list(safe_dict(features.open_interest).get("risk_flags")) if x]
    risk_flags = build_risk_flags(liquidity_state=liquidity_state, crowding_out=crowding_out, oi_flags=oi_flags)

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

    trend = infer_trend(direction_bias)
    phase = infer_phase(market_phase)
    timeframe_alignment = infer_timeframe_alignment(horizon_alignment)
    strength = infer_strength(trend_strength, horizon_alignment, market_fragility)

    dominant_pressure = infer_dominant_pressure(direction_bias)
    orderbook_bias = infer_orderbook_bias(safe_text(safe_dict(features.orderbook).get("stability")))
    squeeze_flag = "liquidation_cluster" in set(risk_flags)
    liquidity_risk = infer_liquidity_risk(squeeze_flag, direction_bias)
    liquidation_proximity = infer_liquidation_proximity(squeeze_flag)

    oi_trend = infer_oi_trend(safe_text(safe_dict(features.open_interest).get("oi_trend")))
    crowding = infer_crowding(crowding_out, direction_bias)

    expansion_risk = infer_expansion_risk(volatility_state, participant_behavior)
    vol_dir = infer_volatility_direction(direction_bias)

    cascade_risk = infer_cascade_risk(market_fragility)
    squeeze_probability = infer_squeeze_probability(
        liquidity_risk=liquidity_risk,
        anomaly_flags=anomaly_flags,
        crowding_out=crowding_out,
        volatility_state=volatility_state,
    )
    reversal_risk = infer_reversal_risk(
        horizon_alignment=horizon_alignment,
        phase=phase,
        volatility_state=volatility_state,
    )

    range_state = infer_range_state(regime)
    trend_structure = infer_trend_structure(direction_bias)

    parts: List[str] = []
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

    return MarketStateMSL(
        version=2,
        timestamp=_iso_utc_from_ms(int(features.ts)),
        symbol=features.symbol,
        market_regime=MarketRegime(
            trend=trend,
            phase=phase,
            timeframe_alignment=timeframe_alignment,
            strength=float(strength),
        ),
        liquidity=LiquidityState(
            dominant_pressure=dominant_pressure,
            liquidity_risk=liquidity_risk,
            orderbook_bias=orderbook_bias,
            liquidation_proximity=liquidation_proximity,
        ),
        positioning=PositioningState(
            crowding=crowding,
            whale_bias="unknown",
            retail_bias="unknown",
            oi_trend=oi_trend,
        ),
        volatility=VolatilityState(
            volatility_regime=volatility_state,
            expansion_risk=expansion_risk,
            volatility_direction=vol_dir,
        ),
        risk=RiskState(
            cascade_risk=cascade_risk,
            squeeze_probability=squeeze_probability,
            reversal_risk=reversal_risk,
        ),
        market_structure=StructureState(
            support_strength="unknown",
            resistance_strength="unknown",
            range_state=range_state,
            trend_structure=trend_structure,
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
        },
    )
