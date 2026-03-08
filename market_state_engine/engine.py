from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

import datetime

from .contracts import KeyLevels, LiquidityState, MarketRegime, MarketStateMSL, PositioningState, RiskState, SentimentState, StructureState, VolatilityState
from .ports.storage.feature_store import FeatureStore


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _safe_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _safe_text(x: Any) -> str:
    try:
        return str(x or "")
    except Exception:
        return ""


def _iso_utc_from_ms(ms: int) -> str:
    try:
        dt = datetime.datetime.fromtimestamp(float(ms) / 1000.0, tz=datetime.timezone.utc).replace(microsecond=0)
    except Exception:
        dt = datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")



@dataclass(frozen=True)
class MarketStateFeatures:

    exchange: str
    symbol: str
    ts: int

    horizons: Dict[str, Any]
    orderbook: Dict[str, Any]
    open_interest: Dict[str, Any]

    anomalies: Dict[str, Any]
    evidence: Dict[str, Any]
    derived: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "ts": self.ts,
            "horizons": dict(self.horizons),
            "orderbook": dict(self.orderbook),
            "open_interest": dict(self.open_interest),
            "anomalies": dict(self.anomalies),
            "evidence": dict(self.evidence),
            "derived": dict(self.derived),
        }


class MarketStateEngine:
    """市场状态引擎：raw_structure -> feature_aggregation -> anomaly_detection -> evidence_extraction -> state_inference -> MSL。"""

    def __init__(self, *, feature_store: Optional[FeatureStore] = None) -> None:
        self._feature_store = feature_store

    def aggregate_features(self, *, exchange: str, symbol: str, market_structure: Dict[str, Any]) -> MarketStateFeatures:
        now_ts = int(time.time() * 1000)

        fused = _safe_dict(_safe_dict(market_structure.get("horizons")).get("fused"))
        hz = _safe_dict(fused.get("horizons"))
        short_hz = _safe_dict(hz.get("short_term"))
        mid_hz = _safe_dict(hz.get("mid_term"))
        long_hz = _safe_dict(hz.get("long_term"))

        pre = _safe_dict(market_structure.get("pre_decision_structure"))
        st = _safe_dict(pre.get("short_term"))
        mt = _safe_dict(pre.get("mid_term"))
        lt = _safe_dict(pre.get("long_term"))

        micro = _safe_dict(st.get("micro_liquidity"))
        ob_meta = _safe_dict(micro.get("meta"))
        ob_risk_flags = _safe_dict(micro.get("risk_flags"))
        st_risks = _safe_dict(st.get("structural_risks"))

        pp = _safe_dict(mt.get("participant_positioning"))
        oi_delta = _safe_dict(pp.get("oi_delta"))
        oi_dyn = _safe_dict(pp.get("oi_dynamics"))
        oi_flags = [str(x) for x in _safe_list(pp.get("risk_flags")) if x]

        short_mb = _safe_dict(short_hz.get("market_background"))
        mid_mb = _safe_dict(mid_hz.get("market_background"))
        mid_pb = _safe_dict(mid_hz.get("participant_background"))
        long_mb = _safe_dict(long_hz.get("market_background"))

        horizons_out = {
            "short_term": {
                "market_background": {
                    "trend_memory": _safe_dict(short_mb.get("trend_memory")),
                    "trend_context": short_mb.get("trend_context"),
                    "structure_state": short_mb.get("structure_state"),
                    "risk_level": short_mb.get("risk_level"),
                    "volatility_state": short_mb.get("volatility_state"),
                },
                "participant_background": _safe_dict(short_hz.get("participant_background")),
                "confidence": float(short_hz.get("confidence") or 0.0),
            },
            "mid_term": {
                "market_background": {
                    "trend_memory": _safe_dict(mid_mb.get("trend_memory")),
                    "trend_context": mid_mb.get("trend_context"),
                    "structure_state": mid_mb.get("structure_state"),
                    "risk_level": mid_mb.get("risk_level"),
                    "volatility_state": mid_mb.get("volatility_state"),
                },
                "participant_background": mid_pb,
                "confidence": float(mid_hz.get("confidence") or 0.0),
            },
            "long_term": {
                "market_background": {
                    "trend_memory": _safe_dict(long_mb.get("trend_memory")),
                    "trend_context": long_mb.get("trend_context"),
                    "structure_state": long_mb.get("structure_state"),
                    "risk_level": long_mb.get("risk_level"),
                    "volatility_state": long_mb.get("volatility_state"),
                },
                "participant_background": _safe_dict(long_hz.get("participant_background")),
                "confidence": float(long_hz.get("confidence") or 0.0),
            },
        }

        orderbook_out = {
            "stability": _safe_text(ob_meta.get("stability")),
            "liquidity_vacuum": bool(st_risks.get("liquidity_vacuum") is True or ob_risk_flags.get("liquidity_vacuum_event") is True),
            "risk_flags": dict(ob_risk_flags),
        }

        open_interest_out = {
            "delta_oi_pct": float(oi_delta.get("delta_oi_pct") or 0.0),
            "oi_trend": _safe_text(oi_dyn.get("oi_trend")),
            "oi_velocity": _safe_text(oi_dyn.get("oi_velocity")),
            "oi_acceleration": _safe_text(oi_dyn.get("oi_acceleration")),
            "risk_flags": list(oi_flags),
        }

        derived = {
            "pre_decision_short_term_structural_risks": dict(st_risks),
            "pre_decision_mid_term_structural_risks": dict(_safe_dict(mt.get("structural_risks"))),
            "pre_decision_long_term_structural_context": dict(_safe_dict(lt.get("structural_context"))),
        }

        return MarketStateFeatures(
            exchange=exchange,
            symbol=symbol,
            ts=now_ts,
            horizons=horizons_out,
            orderbook=orderbook_out,
            open_interest=open_interest_out,
            anomalies={},
            evidence={},
            derived=derived,
        )

    def detect_anomalies(self, *, features: MarketStateFeatures) -> Dict[str, Any]:
        ob = _safe_dict(features.orderbook)
        oi = _safe_dict(features.open_interest)
        derived = _safe_dict(features.derived)

        anomalies: Dict[str, Any] = {"flags": []}

        if bool(ob.get("liquidity_vacuum") is True):
            anomalies["flags"].append("orderbook_liquidity_vacuum")

        try:
            d_pct = float(oi.get("delta_oi_pct") or 0.0)
        except Exception:
            d_pct = 0.0
        if abs(d_pct) >= 0.03:
            anomalies["flags"].append("oi_spike")
            anomalies["oi_spike"] = {"delta_oi_pct": float(d_pct)}

        oi_flags = [str(x) for x in _safe_list(oi.get("risk_flags")) if x]
        if any(x in {"possible_liquidation_or_unwind", "fragile_leverage_build"} for x in oi_flags):
            anomalies["flags"].append("liquidation_cluster")

        lt_ctx = _safe_dict(derived.get("pre_decision_long_term_structural_context"))
        if bool(lt_ctx.get("leverage_extreme") is True):
            anomalies["flags"].append("leverage_extreme")
        cp = _safe_dict(lt_ctx.get("crowding_percentile"))
        zone = _safe_text(cp.get("zone"))
        if zone in ("elevated", "extreme"):
            anomalies["flags"].append("crowding_extreme")

        anomalies["flags"] = sorted(set([str(x) for x in anomalies["flags"] if x]))
        return anomalies

    def extract_evidence(self, *, features: MarketStateFeatures, anomalies: Dict[str, Any]) -> Dict[str, Any]:
        """提取可解释证据层：面向 LLM 与调试输出，保持字段少且稳定。"""

        mid = _safe_dict(features.horizons.get("mid_term"))
        mid_mb = _safe_dict(mid.get("market_background"))
        mid_tm = _safe_dict(mid_mb.get("trend_memory"))
        mid_pb = _safe_dict(mid.get("participant_background"))

        ob = _safe_dict(features.orderbook)
        oi = _safe_dict(features.open_interest)

        return {
            "price_direction_mid": _safe_text(mid_tm.get("price_direction")),
            "price_strength_mid": _safe_text(mid_tm.get("price_strength")),
            "volatility_state_mid": _safe_text(mid_mb.get("volatility_state")),
            "crowding_mid": _safe_text(mid_pb.get("crowding")),
            "participant_stability_mid": _safe_text(mid_pb.get("stability")),
            "liquidity_vacuum": bool(ob.get("liquidity_vacuum") is True),
            "orderbook_stability": _safe_text(ob.get("stability")),
            "oi_trend": _safe_text(oi.get("oi_trend")),
            "oi_velocity": _safe_text(oi.get("oi_velocity")),
            "oi_acceleration": _safe_text(oi.get("oi_acceleration")),
            "delta_oi_pct": float(oi.get("delta_oi_pct") or 0.0),
            "anomaly_flags": [str(x) for x in _safe_list(_safe_dict(anomalies).get("flags")) if x],
        }

    def infer_msl(self, *, features: MarketStateFeatures) -> MarketStateMSL:
        mid = _safe_dict(features.horizons.get("mid_term"))
        short = _safe_dict(features.horizons.get("short_term"))

        mid_mb = _safe_dict(mid.get("market_background"))
        short_mb = _safe_dict(short.get("market_background"))
        mid_tm = _safe_dict(mid_mb.get("trend_memory"))
        short_tm = _safe_dict(short_mb.get("trend_memory"))

        dir_raw = _safe_text(mid_tm.get("price_direction"))
        if dir_raw == "up":
            direction_bias: Literal["bullish", "bearish", "neutral", "unknown"] = "bullish"
        elif dir_raw == "down":
            direction_bias = "bearish"
        elif dir_raw in ("flat", "neutral"):
            direction_bias = "neutral"
        elif dir_raw:
            direction_bias = "unknown"
        else:
            direction_bias = "unknown"

        trend_strength = _safe_text(mid_tm.get("price_strength"))
        if trend_strength not in ("strong", "medium", "weak"):
            trend_strength = "unknown"

        vol = _safe_text(mid_mb.get("volatility_state"))
        if vol == "medium":
            volatility_state: Literal["low", "normal", "high", "unknown"] = "normal"
        elif vol in ("low", "high"):
            volatility_state = vol  # type: ignore[assignment]
        else:
            stability = _safe_text(_safe_dict(mid.get("participant_background")).get("stability"))
            if stability == "volatile":
                volatility_state = "high"
            elif stability == "stable":
                volatility_state = "low"
            elif stability:
                volatility_state = "normal"
            else:
                volatility_state = "unknown"

        crowding = _safe_text(_safe_dict(mid.get("participant_background")).get("crowding"))
        if crowding in ("high", "low", "insufficient_evidence"):
            crowding_out = crowding
        elif crowding:
            crowding_out = "normal"
        else:
            crowding_out = "unknown"

        s_dir = _safe_text(short_tm.get("price_direction"))
        m_dir = _safe_text(mid_tm.get("price_direction"))
        s_str = _safe_text(short_tm.get("price_strength"))
        m_str = _safe_text(mid_tm.get("price_strength"))
        if not s_dir or not m_dir:
            horizon_alignment: Literal["aligned", "mixed", "conflict", "unknown"] = "unknown"
        elif s_dir == "flat" or m_dir == "flat":
            horizon_alignment = "mixed"
        elif s_dir == m_dir:
            if s_str in ("strong", "medium") and m_str in ("strong", "medium"):
                horizon_alignment = "aligned"
            else:
                horizon_alignment = "mixed"
        else:
            horizon_alignment = "conflict"

        s_ctx = _safe_text(_safe_dict(short_mb.get("trend_context") or {}).get("label"))
        m_ctx = _safe_text(_safe_dict(mid_mb.get("trend_context") or {}).get("label"))
        blob = (s_ctx + " " + m_ctx).lower()
        if "breakdown" in blob or "break" in blob:
            regime: Literal["trend", "range", "transition", "breakdown", "unknown"] = "breakdown"
        elif "range" in blob or "consolidation" in blob or "chop" in blob:
            regime = "range"
        elif horizon_alignment == "conflict":
            regime = "transition"
        elif "trend" in blob or "continuation" in blob or "directional" in blob:
            regime = "trend"
        else:
            regime = "unknown"

        liquidity_state: Literal["deep", "normal", "thin", "unknown"]
        if bool(_safe_dict(features.orderbook).get("liquidity_vacuum") is True):
            liquidity_state = "thin"
        else:
            stability = _safe_text(_safe_dict(features.orderbook).get("stability"))
            if stability == "fragile":
                liquidity_state = "thin"
            elif stability == "stable":
                liquidity_state = "normal"
            elif stability:
                liquidity_state = "normal"
            else:
                liquidity_state = "unknown"

        d_pct = float(_safe_dict(features.open_interest).get("delta_oi_pct") or 0.0)
        velocity = _safe_text(_safe_dict(features.open_interest).get("oi_velocity"))
        if abs(d_pct) < 0.003 or velocity not in ("medium", "high"):
            participant_behavior: Literal["adding_leverage", "reducing_leverage", "rotation", "unclear", "unknown"] = "unclear"
        elif d_pct > 0:
            participant_behavior = "adding_leverage"
        else:
            participant_behavior = "reducing_leverage"

        risk_flags: List[str] = []
        if liquidity_state == "thin":
            risk_flags.append("liquidity_vacuum")
        if crowding_out == "high":
            risk_flags.append("crowding")
        oi_flags = [str(x) for x in _safe_list(_safe_dict(features.open_interest).get("risk_flags")) if x]
        if any(x in {"possible_liquidation_or_unwind", "fragile_leverage_build"} for x in oi_flags):
            risk_flags.append("liquidation_cluster")
        risk_flags.extend(oi_flags)
        risk_flags = sorted(set([x for x in risk_flags if x]))

        anomaly_flags = [str(x) for x in _safe_list(_safe_dict(features.anomalies).get("flags")) if x]
        fragility_score = 0
        if "orderbook_liquidity_vacuum" in set(anomaly_flags) or liquidity_state == "thin":
            fragility_score += 2
        if "liquidation_cluster" in set(anomaly_flags) or "leverage_extreme" in set(anomaly_flags):
            fragility_score += 2
        if volatility_state == "high":
            fragility_score += 1
        if crowding_out == "high":
            fragility_score += 1
        if fragility_score >= 4:
            market_fragility: Literal["low", "medium", "high", "unknown"] = "high"
        elif fragility_score >= 2:
            market_fragility = "medium"
        elif fragility_score >= 0:
            market_fragility = "low"
        else:
            market_fragility = "unknown"

        if regime == "trend" and participant_behavior == "adding_leverage" and volatility_state != "high":
            market_phase: Literal["expansion", "distribution", "contraction", "accumulation", "unknown"] = "expansion"
        elif crowding_out == "high" and volatility_state in ("high", "normal") and regime in ("trend", "transition"):
            market_phase = "distribution"
        elif participant_behavior == "reducing_leverage" and regime in ("breakdown", "transition"):
            market_phase = "contraction"
        elif regime == "range" and participant_behavior in ("unclear", "reducing_leverage") and volatility_state in ("low", "normal"):
            market_phase = "accumulation"
        else:
            market_phase = "unknown"

        if trend_strength == "strong":
            strength = 0.78
        elif trend_strength == "medium":
            strength = 0.6
        elif trend_strength == "weak":
            strength = 0.42
        else:
            strength = 0.0
        if horizon_alignment == "conflict":
            strength = min(strength, 0.45)
        if market_fragility in ("medium", "high"):
            strength = min(strength, 0.55 if market_fragility == "medium" else 0.45)

        if direction_bias == "bullish":
            trend: Literal["bullish", "bearish", "sideways", "unknown"] = "bullish"
        elif direction_bias == "bearish":
            trend = "bearish"
        elif direction_bias == "neutral":
            trend = "sideways"
        else:
            trend = "unknown"

        if market_phase == "expansion":
            phase: Literal["impulse", "continuation", "exhaustion", "accumulation", "distribution", "unknown"] = "continuation"
        elif market_phase == "distribution":
            phase = "distribution"
        elif market_phase == "contraction":
            phase = "exhaustion"
        elif market_phase == "accumulation":
            phase = "accumulation"
        else:
            phase = "unknown"

        if horizon_alignment == "aligned":
            timeframe_alignment: Literal["aligned", "mixed", "conflicting", "unknown"] = "aligned"
        elif horizon_alignment == "mixed":
            timeframe_alignment = "mixed"
        elif horizon_alignment == "conflict":
            timeframe_alignment = "conflicting"
        else:
            timeframe_alignment = "unknown"

        if direction_bias == "bullish":
            dominant_pressure: Literal["buyers", "sellers", "balanced", "unknown"] = "buyers"
        elif direction_bias == "bearish":
            dominant_pressure = "sellers"
        elif direction_bias == "neutral":
            dominant_pressure = "balanced"
        else:
            dominant_pressure = "unknown"

        ob_stability = _safe_text(_safe_dict(features.orderbook).get("stability"))
        if ob_stability in ("stable", "fragile"):
            orderbook_bias: Literal["bid_heavy", "ask_heavy", "neutral", "unknown"] = "neutral"
        elif ob_stability:
            orderbook_bias = "neutral"
        else:
            orderbook_bias = "unknown"

        squeeze_flag = "liquidation_cluster" in set(risk_flags)
        if squeeze_flag and direction_bias == "bullish":
            liquidity_risk: Literal["short_squeeze", "long_squeeze", "neutral", "unknown"] = "short_squeeze"
        elif squeeze_flag and direction_bias == "bearish":
            liquidity_risk = "long_squeeze"
        elif squeeze_flag:
            liquidity_risk = "unknown"
        else:
            liquidity_risk = "neutral"

        if squeeze_flag:
            liquidation_proximity: Literal["above", "below", "both", "none", "unknown"] = "unknown"
        else:
            liquidation_proximity = "none"

        oi_trend_raw = _safe_text(_safe_dict(features.open_interest).get("oi_trend"))
        if oi_trend_raw in ("expanding", "contracting", "flat"):
            oi_trend: Literal["expanding", "contracting", "flat", "unknown"] = oi_trend_raw  # type: ignore[assignment]
        else:
            oi_trend = "unknown"

        if crowding_out == "high" and direction_bias == "bullish":
            crowding: Literal["crowded_long", "crowded_short", "balanced", "unknown"] = "crowded_long"
        elif crowding_out == "high" and direction_bias == "bearish":
            crowding = "crowded_short"
        elif crowding_out in ("normal", "low"):
            crowding = "balanced"
        elif crowding_out:
            crowding = "unknown"
        else:
            crowding = "unknown"

        if volatility_state == "low":
            expansion_risk: Literal["expanding", "compressing", "unknown"] = "compressing"
        elif volatility_state == "high":
            expansion_risk = "expanding"
        elif participant_behavior == "adding_leverage":
            expansion_risk = "expanding"
        else:
            expansion_risk = "unknown"

        if direction_bias == "bullish":
            vol_dir: Literal["upside", "downside", "neutral", "unknown"] = "upside"
        elif direction_bias == "bearish":
            vol_dir = "downside"
        elif direction_bias == "neutral":
            vol_dir = "neutral"
        else:
            vol_dir = "unknown"

        if market_fragility in ("low", "medium", "high"):
            cascade_risk: Literal["high", "medium", "low", "unknown"] = market_fragility  # type: ignore[assignment]
        else:
            cascade_risk = "unknown"

        squeeze_score = 0
        if liquidity_risk in ("short_squeeze", "long_squeeze"):
            squeeze_score += 2
        if "crowding_extreme" in set(anomaly_flags):
            squeeze_score += 2
        if "leverage_extreme" in set(anomaly_flags):
            squeeze_score += 2
        if crowding_out == "high":
            squeeze_score += 1
        if volatility_state == "high":
            squeeze_score += 1
        if squeeze_score >= 4:
            squeeze_probability: Literal["high", "medium", "low", "unknown"] = "high"
        elif squeeze_score >= 2:
            squeeze_probability = "medium"
        else:
            squeeze_probability = "low"

        reversal_score = 0
        if horizon_alignment == "conflict":
            reversal_score += 2
        if phase in ("distribution", "exhaustion"):
            reversal_score += 1
        if volatility_state == "high":
            reversal_score += 1
        if reversal_score >= 3:
            reversal_risk: Literal["high", "medium", "low", "unknown"] = "high"
        elif reversal_score >= 2:
            reversal_risk = "medium"
        else:
            reversal_risk = "low"

        if regime == "range":
            range_state: Literal["breakout", "range", "breakdown", "unknown"] = "range"
        elif regime == "breakdown":
            range_state = "breakdown"
        elif regime == "trend":
            range_state = "breakout"
        else:
            range_state = "unknown"

        if direction_bias == "bullish":
            trend_structure: Literal["hh_hl", "lh_ll", "mixed", "unknown"] = "hh_hl"
        elif direction_bias == "bearish":
            trend_structure = "lh_ll"
        elif direction_bias == "neutral":
            trend_structure = "mixed"
        else:
            trend_structure = "unknown"

        sentiment = SentimentState(
            funding_sentiment="unknown",
            social_sentiment="unknown",
            news_bias="unknown",
            overall_sentiment="unknown",
        )

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
            sentiment=sentiment,
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

    def build(self, *, exchange: str, symbol: str, market_structure: Dict[str, Any]) -> Tuple[MarketStateMSL, MarketStateFeatures]:
        feats0 = None
        if self._feature_store is not None:
            feats0 = self._feature_store.get(exchange, symbol)
        if feats0 is None:
            feats0 = self.aggregate_features(exchange=exchange, symbol=symbol, market_structure=market_structure)
            if self._feature_store is not None:
                self._feature_store.put(feats0)
        anomalies = self.detect_anomalies(features=feats0)
        evidence = self.extract_evidence(features=feats0, anomalies=anomalies)
        feats = MarketStateFeatures(
            exchange=feats0.exchange,
            symbol=feats0.symbol,
            ts=feats0.ts,
            horizons=feats0.horizons,
            orderbook=feats0.orderbook,
            open_interest=feats0.open_interest,
            anomalies=anomalies,
            evidence=evidence,
            derived=feats0.derived,
        )
        msl = self.infer_msl(features=feats)
        return msl, feats
