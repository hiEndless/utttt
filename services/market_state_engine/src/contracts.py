from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal


@dataclass(frozen=True)
class MarketRegime:
    trend: Literal["bullish", "bearish", "sideways", "unknown"]
    phase: Literal["impulse", "continuation", "exhaustion", "accumulation", "distribution", "unknown"]
    timeframe_alignment: Literal["aligned", "mixed", "conflicting", "unknown"]
    strength: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trend": self.trend,
            "phase": self.phase,
            "timeframe_alignment": self.timeframe_alignment,
            "strength": float(self.strength),
        }


@dataclass(frozen=True)
class LiquidityState:
    dominant_pressure: Literal["buyers", "sellers", "balanced", "unknown"]
    liquidity_risk: Literal["short_squeeze", "long_squeeze", "neutral", "unknown"]
    orderbook_bias: Literal["bid_heavy", "ask_heavy", "neutral", "unknown"]
    liquidation_proximity: Literal["above", "below", "both", "none", "unknown"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dominant_pressure": self.dominant_pressure,
            "liquidity_risk": self.liquidity_risk,
            "orderbook_bias": self.orderbook_bias,
            "liquidation_proximity": self.liquidation_proximity,
        }


@dataclass(frozen=True)
class PositioningState:
    crowding: Literal["crowded_long", "crowded_short", "balanced", "unknown"]
    whale_bias: Literal["long", "short", "neutral", "unknown"]
    retail_bias: Literal["long", "short", "neutral", "unknown"]
    oi_trend: Literal["expanding", "contracting", "flat", "unknown"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "crowding": self.crowding,
            "whale_bias": self.whale_bias,
            "retail_bias": self.retail_bias,
            "oi_trend": self.oi_trend,
        }


@dataclass(frozen=True)
class VolatilityState:
    volatility_regime: Literal["low", "normal", "high", "unknown"]
    expansion_risk: Literal["expanding", "compressing", "unknown"]
    volatility_direction: Literal["upside", "downside", "neutral", "unknown"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "volatility_regime": self.volatility_regime,
            "expansion_risk": self.expansion_risk,
            "volatility_direction": self.volatility_direction,
        }


@dataclass(frozen=True)
class RiskState:
    cascade_risk: Literal["high", "medium", "low", "unknown"]
    squeeze_probability: Literal["high", "medium", "low", "unknown"]
    reversal_risk: Literal["high", "medium", "low", "unknown"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cascade_risk": self.cascade_risk,
            "squeeze_probability": self.squeeze_probability,
            "reversal_risk": self.reversal_risk,
        }


@dataclass(frozen=True)
class StructureState:
    support_strength: Literal["strong", "medium", "weak", "unknown"]
    resistance_strength: Literal["strong", "medium", "weak", "unknown"]
    range_state: Literal["breakout", "range", "breakdown", "unknown"]
    trend_structure: Literal["hh_hl", "lh_ll", "mixed", "unknown"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "support_strength": self.support_strength,
            "resistance_strength": self.resistance_strength,
            "range_state": self.range_state,
            "trend_structure": self.trend_structure,
        }


@dataclass(frozen=True)
class KeyLevels:
    major_support: List[float] = field(default_factory=list)
    major_resistance: List[float] = field(default_factory=list)
    liquidation_clusters: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "major_support": [float(x) for x in list(self.major_support or [])],
            "major_resistance": [float(x) for x in list(self.major_resistance or [])],
            "liquidation_clusters": [float(x) for x in list(self.liquidation_clusters or [])],
        }


@dataclass(frozen=True)
class MarketStateMSL:
    """Market State Language（MSL）：面向下游消费的稳定语义层。"""

    version: int
    timestamp: str
    symbol: str

    market_regime: MarketRegime
    liquidity: LiquidityState
    positioning: PositioningState
    volatility: VolatilityState
    risk: RiskState
    market_structure: StructureState

    key_levels: KeyLevels = field(default_factory=KeyLevels)
    anomalies: List[str] = field(default_factory=list)
    summary: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_llm_dict(self) -> Dict[str, Any]:
        return {
            "version": int(self.version),
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "market_regime": self.market_regime.to_dict(),
            "liquidity_state": self.liquidity.to_dict(),
            "positioning_state": self.positioning.to_dict(),
            "volatility_state": self.volatility.to_dict(),
            "market_risk_state": self.risk.to_dict(),
            "market_structure_state": self.market_structure.to_dict(),
            "key_levels": self.key_levels.to_dict(),
            "anomalies": [str(x) for x in list(self.anomalies or []) if x],
            "summary": str(self.summary or ""),
        }

    @property
    def ts(self) -> int:
        s = str(self.timestamp or "")
        if not s:
            return 0
        try:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return int(dt.timestamp() * 1000)
        except Exception:
            return 0

    @property
    def direction_bias(self) -> Literal["bullish", "bearish", "neutral", "unknown"]:
        t = self.market_regime.trend
        if t == "bullish":
            return "bullish"
        if t == "bearish":
            return "bearish"
        if t == "sideways":
            return "neutral"
        return "unknown"

    @property
    def trend_strength(self) -> Literal["strong", "medium", "weak", "unknown"]:
        x = float(self.market_regime.strength)
        if x >= 0.7:
            return "strong"
        if x >= 0.45:
            return "medium"
        if x > 0:
            return "weak"
        return "unknown"

    @property
    def horizon_alignment(self) -> Literal["aligned", "mixed", "conflict", "unknown"]:
        ta = self.market_regime.timeframe_alignment
        if ta == "aligned":
            return "aligned"
        if ta == "mixed":
            return "mixed"
        if ta == "conflicting":
            return "conflict"
        return "unknown"

    @property
    def regime(self) -> Literal["trend", "range", "transition", "breakdown", "unknown"]:
        if self.market_structure.range_state == "range":
            return "range"
        if self.market_structure.range_state == "breakdown":
            return "breakdown"
        if self.market_regime.timeframe_alignment == "conflicting":
            return "transition"
        if self.market_regime.trend in ("bullish", "bearish") and self.market_regime.phase != "unknown":
            return "trend"
        return "unknown"

    @property
    def market_phase(self) -> Literal["expansion", "distribution", "contraction", "accumulation", "unknown"]:
        p = self.market_regime.phase
        if p in ("impulse", "continuation"):
            return "expansion"
        if p == "distribution":
            return "distribution"
        if p == "exhaustion":
            return "contraction"
        if p == "accumulation":
            return "accumulation"
        return "unknown"

    @property
    def market_fragility(self) -> Literal["low", "medium", "high", "unknown"]:
        c = self.risk.cascade_risk
        if c in ("low", "medium", "high"):
            return c
        return "unknown"
