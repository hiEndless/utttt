from __future__ import annotations

import asyncio
from typing import Any, Dict, Mapping

from feature_service.ports.behavior_provider import BehaviorProvider
from feature_service.ports.horizons_provider import HorizonsProvider
from feature_service.ports.indicators_provider import IndicatorsProvider
from feature_service.ports.open_interest_provider import OpenInterestProvider
from feature_service.ports.orderbook_provider import OrderbookProvider
from feature_service.normalizers.response_normalizer import (
    normalize_degraded_reasons,
    normalize_exchange,
    normalize_features_payload,
    normalize_raw_market_structure,
    normalize_symbol,
)
from feature_service.providers.bundle import ProviderBundle
from feature_service.providers.degradation_state import reset_degradation_state, snapshot_degradation_reasons


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _safe_list(x: Any) -> list[Any]:
    return x if isinstance(x, list) else []


class FeatureDataUnavailableError(RuntimeError):
    """关键结构数据不可用时抛出，交由路由层映射为标准 HTTP 错误。"""

    def __init__(self, *, exchange: str, symbol: str, degraded_reasons: list[str]) -> None:
        self.exchange = exchange
        self.symbol = symbol
        self.degraded_reasons = degraded_reasons
        super().__init__("feature_data_unavailable")


def _confidence_from_level(level: str) -> Dict[str, Any]:
    lv = str(level or "low")
    if lv not in ("high", "medium", "low"):
        lv = "low"
    score_map = {"high": 0.85, "medium": 0.65, "low": 0.35}
    return {"level": lv, "score": float(score_map.get(lv, 0.35))}


def _confidence_from_score(score: float) -> Dict[str, Any]:
    sc = float(score)
    if sc >= 0.75:
        lv = "high"
    elif sc >= 0.5:
        lv = "medium"
    else:
        lv = "low"
    return {"level": lv, "score": float(round(sc, 4))}


def _build_micro_liquidity(orderbook_out: Mapping[str, Any], include_snapshot: bool) -> Dict[str, Any]:
    snapshot = _safe_dict(orderbook_out.get("orderbook_snapshot"))
    structure_short = _safe_dict(orderbook_out.get("orderbook_structure_short"))
    risk_flags = _safe_dict(orderbook_out.get("orderbook_risk_flags"))

    stability = str(structure_short.get("liquidity_stability") or "unknown")
    if stability not in ("stable", "fragile", "unknown"):
        stability = "unknown"

    conf_score = 0.5
    if stability == "stable":
        conf_score = 0.8
    elif stability == "fragile":
        conf_score = 0.7

    out: Dict[str, Any] = {
        "orderbook_structure": structure_short,
        "risk_flags": risk_flags,
        "meta": {"stability": stability},
        "confidence": _confidence_from_score(conf_score),
    }
    if include_snapshot:
        out["orderbook_snapshot"] = snapshot
    return out


def _build_participant_positioning(open_interest_out: Mapping[str, Any], horizon: str) -> Dict[str, Any]:
    struct = open_interest_out.get("open_interest_structure") if isinstance(open_interest_out, Mapping) else None
    open_interest_structure = struct if isinstance(struct, Mapping) else {}

    intervals_by_horizon = {
        "short_term": ["5m", "15m", "30m", "1h"],
        "mid_term": ["2h", "4h", "6h", "12h"],
        "long_term": ["6h", "12h", "1d"],
    }
    selected_itv = None
    cell: Dict[str, Any] = {}
    for itv in intervals_by_horizon.get(horizon, []):
        candidate = _safe_dict(open_interest_structure.get(itv))
        if candidate:
            selected_itv = itv
            cell = candidate
            if horizon != "long_term":
                break

    meta = _safe_dict(cell.get("meta"))
    inf = _safe_dict(cell.get("participant_inference"))
    confidence_level = str(inf.get("confidence") or "low")
    if confidence_level not in ("high", "medium", "low"):
        confidence_level = "low"

    participant_inference = dict(inf)
    participant_inference.pop("confidence", None)
    if participant_inference:
        participant_inference["confidence"] = _confidence_from_level(confidence_level)

    oi_state_raw = _safe_dict(cell.get("state"))
    oi_delta_raw = _safe_dict(cell.get("delta"))
    oi_dynamics_raw = _safe_dict(cell.get("dynamics"))
    coupling_raw = _safe_dict(cell.get("coupling"))

    structural_weight = str(meta.get("structural_weight") or "low")
    if structural_weight not in ("high", "low"):
        structural_weight = "low"
    if horizon == "long_term":
        structural_weight = "veto_only"

    return {
        "oi_state": {
            "open_interest": _safe_float(oi_state_raw.get("open_interest"), default=0.0),
            "open_interest_value": _safe_float(oi_state_raw.get("open_interest_value"), default=0.0),
            "oi_to_quote_volume_ratio": _safe_float(oi_state_raw.get("oi_to_quote_volume_ratio"), default=0.0),
        },
        "oi_delta": {
            "delta_oi": _safe_float(oi_delta_raw.get("delta_oi"), default=0.0),
            "delta_oi_pct": _safe_float(oi_delta_raw.get("delta_oi_pct"), default=0.0),
        },
        "oi_dynamics": {
            "oi_trend": str(oi_dynamics_raw.get("oi_trend") or "unknown"),
            "oi_velocity": str(oi_dynamics_raw.get("oi_velocity") or "unknown"),
            "oi_acceleration": str(oi_dynamics_raw.get("oi_acceleration") or "unknown"),
        },
        "coupling": {
            "price_trend": str(coupling_raw.get("price_trend") or "unknown"),
            "taker_bias": str(coupling_raw.get("taker_bias") or "unknown"),
            **({"agg_trade_mode": str(coupling_raw.get("agg_trade_mode"))} if coupling_raw.get("agg_trade_mode") else {}),
        },
        "interpretation_tags": [str(t) for t in list(cell.get("interpretation_tags") or []) if t],
        "risk_flags": [str(r) for r in list(cell.get("risk_flags") or []) if r],
        "participant_inference": participant_inference,
        "structural_weight": structural_weight,
        "confidence": _confidence_from_level(confidence_level),
        "meta": {"selected_interval": selected_itv, "selected_latest_ts": int(meta.get("latest_ts") or 0)},
    }


def _build_behavioral_intent(behavior_out: Mapping[str, Any], horizon: str) -> Dict[str, Any]:
    bs_all = behavior_out.get("behavioral_structure") if isinstance(behavior_out, Mapping) else None
    bs = _safe_dict(_safe_dict(bs_all).get(horizon))
    summary_dict = _safe_dict(bs.get("summary"))
    status = str(bs.get("status") or "unknown")

    tags = []
    for key in ("dominant_flow", "market_mode", "range_stability"):
        value = summary_dict.get(key)
        if value:
            tags.append(f"{key}_{value}")
    for value in list(summary_dict.get("risk_flags") or []):
        if value:
            tags.append(str(value))
    if status and status not in ("mature", "ok"):
        tags.append(f"status_{status}")

    confidence_level = str(summary_dict.get("flow_confidence") or "low")
    if confidence_level not in ("high", "medium", "low"):
        confidence_level = "low"

    taker_bias: Dict[str, Any] = {}
    if summary_dict:
        taker_bias = {
            "dominant_flow": summary_dict.get("dominant_flow"),
            "flow_confidence": summary_dict.get("flow_confidence"),
            "market_mode": summary_dict.get("market_mode"),
            "range_stability": summary_dict.get("range_stability"),
        }

    return {
        "taker_bias": taker_bias,
        "interpretation_tags": sorted(set([t for t in tags if t])),
        "confidence": _confidence_from_level(confidence_level),
    }


def _build_structural_risks(orderbook_out: Mapping[str, Any], horizons_out: Mapping[str, Any], horizon: str) -> Dict[str, Any]:
    risk_flags = _safe_dict(orderbook_out.get("orderbook_risk_flags"))
    liquidity_vacuum = bool(risk_flags.get("liquidity_vacuum_event") is True)

    crowding_risk = "unknown"
    fused = _safe_dict(horizons_out.get("fused"))
    hz_block = _safe_dict(_safe_dict(fused.get("horizons")).get(horizon))
    pb = _safe_dict(hz_block.get("participant_background"))
    crowding = str(pb.get("crowding") or "")
    if crowding == "high":
        crowding_risk = "high"
    elif crowding == "low":
        crowding_risk = "low"

    return {"liquidity_vacuum": liquidity_vacuum, "crowding_risk": crowding_risk}


def _build_long_term_structural_context(open_interest_out: Mapping[str, Any], horizons_out: Mapping[str, Any]) -> Dict[str, Any]:
    pp = _build_participant_positioning(open_interest_out, "long_term")
    oi_delta = _safe_dict(pp.get("oi_delta"))
    oi_dynamics = _safe_dict(pp.get("oi_dynamics"))
    risk_flags = set([str(x) for x in list(pp.get("risk_flags") or []) if x])

    delta_pct = abs(_safe_float(oi_delta.get("delta_oi_pct"), default=0.0))
    velocity = str(oi_dynamics.get("oi_velocity") or "unknown")
    trend = str(oi_dynamics.get("oi_trend") or "unknown")

    leverage_extreme = False
    if delta_pct >= 0.03 and velocity in ("medium", "high"):
        leverage_extreme = True
    if "fragile_leverage_build" in risk_flags or "possible_liquidation_or_unwind" in risk_flags:
        leverage_extreme = True

    if trend == "flat":
        trend_maturity = "early"
    elif velocity == "high" and delta_pct >= 0.03:
        trend_maturity = "late"
    elif velocity in ("medium", "high"):
        trend_maturity = "mid"
    else:
        trend_maturity = "early"

    crowding_percentile = 0.5
    fused = _safe_dict(horizons_out.get("fused"))
    hz_block = _safe_dict(_safe_dict(_safe_dict(fused.get("horizons")).get("long_term")))
    pb = _safe_dict(hz_block.get("participant_background"))
    crowding = str(pb.get("crowding") or "")
    p_state = str(pb.get("participant_state") or "")
    if crowding == "high" or ("crowded" in p_state.lower()):
        crowding_percentile = 0.9
    elif crowding == "low":
        crowding_percentile = 0.2

    if crowding_percentile < 0.3:
        crowding_zone = "low"
    elif crowding_percentile < 0.8:
        crowding_zone = "normal"
    elif crowding_percentile < 0.95:
        crowding_zone = "elevated"
    else:
        crowding_zone = "extreme"

    conf = _safe_dict(pp.get("confidence"))
    score = float(conf.get("score") or 0.35)
    if leverage_extreme and crowding_percentile >= 0.8:
        score = max(score, 0.65)
    confidence = _confidence_from_score(score) if score >= 0.75 else _confidence_from_level(str(conf.get("level") or "medium"))

    return {
        "trend_maturity": trend_maturity,
        "leverage_extreme": bool(leverage_extreme),
        "crowding_percentile": {"value": float(round(crowding_percentile, 3)), "zone": crowding_zone},
        "confidence": confidence,
    }


def _derive_indicator_metrics(indicators: Mapping[str, Any]) -> Dict[str, Any]:
    intervals: Dict[str, Any] = {}
    inventory: set[str] = set()
    populated_intervals = 0
    for interval, payload in (indicators or {}).items():
        block = _safe_dict(payload)
        if not block:
            continue
        names = sorted([str(k) for k, v in block.items() if v is not None])
        if not names:
            continue
        populated_intervals += 1
        inventory.update(names)
        intervals[str(interval)] = {
            "indicator_names": names,
            "indicator_count": len(names),
        }
    return {
        "interval_count": populated_intervals,
        "indicator_inventory": sorted(inventory),
        "by_interval": intervals,
    }


def _derive_horizon_metrics(horizons_out: Mapping[str, Any]) -> Dict[str, Any]:
    fused = _safe_dict(horizons_out.get("fused"))
    hz = _safe_dict(fused.get("horizons"))
    out: Dict[str, Any] = {}
    for horizon in ("short_term", "mid_term", "long_term"):
        block = _safe_dict(hz.get(horizon))
        mb = _safe_dict(block.get("market_background"))
        pb = _safe_dict(block.get("participant_background"))
        tm = _safe_dict(mb.get("trend_memory"))
        out[horizon] = {
            "price_direction": str(tm.get("price_direction") or "unknown"),
            "price_strength": str(tm.get("price_strength") or "unknown"),
            "trend_context": _safe_dict(mb.get("trend_context")),
            "volatility_state": str(mb.get("volatility_state") or "unknown"),
            "crowding": str(pb.get("crowding") or "unknown"),
            "participant_state": str(pb.get("participant_state") or "unknown"),
            "confidence": float(block.get("confidence") or 0.0),
        }
    return out


def _derive_orderbook_metrics(orderbook_out: Mapping[str, Any]) -> Dict[str, Any]:
    structure_short = _safe_dict(orderbook_out.get("orderbook_structure_short"))
    risk_flags = _safe_dict(orderbook_out.get("orderbook_risk_flags"))
    return {
        "liquidity_stability": str(structure_short.get("liquidity_stability") or "unknown"),
        "spread_state": str(structure_short.get("spread_state") or "unknown"),
        "depth_state": str(structure_short.get("depth_state") or "unknown"),
        "imbalance_state": str(structure_short.get("imbalance_state") or "unknown"),
        "liquidity_vacuum_event": bool(risk_flags.get("liquidity_vacuum_event") is True),
    }


def _derive_open_interest_metrics(open_interest_out: Mapping[str, Any]) -> Dict[str, Any]:
    consensus = _safe_dict(open_interest_out.get("structure_consensus"))
    structure = _safe_dict(open_interest_out.get("open_interest_structure"))
    representative: Dict[str, Any] = {}
    for interval in ("15m", "1h", "4h", "1d"):
        cell = _safe_dict(structure.get(interval))
        if not cell:
            continue
        representative[interval] = {
            "oi_trend": str(_safe_dict(cell.get("dynamics")).get("oi_trend") or "unknown"),
            "oi_velocity": str(_safe_dict(cell.get("dynamics")).get("oi_velocity") or "unknown"),
            "delta_oi_pct": _safe_float(_safe_dict(cell.get("delta")).get("delta_oi_pct"), default=0.0),
            "risk_flags": [str(x) for x in _safe_list(cell.get("risk_flags")) if x],
        }
    return {
        "structure_consensus": consensus,
        "representative_intervals": representative,
    }


def _derive_behavior_metrics(behavior_out: Mapping[str, Any]) -> Dict[str, Any]:
    structure = _safe_dict(behavior_out.get("behavioral_structure"))
    out: Dict[str, Any] = {}
    for horizon in ("short_term", "mid_term", "long_term"):
        block = _safe_dict(structure.get(horizon))
        summary = _safe_dict(block.get("summary"))
        out[horizon] = {
            "status": str(block.get("status") or "unknown"),
            "dominant_flow": str(summary.get("dominant_flow") or "unknown"),
            "market_mode": str(summary.get("market_mode") or "unknown"),
            "range_stability": str(summary.get("range_stability") or "unknown"),
            "risk_flags": [str(x) for x in _safe_list(summary.get("risk_flags")) if x],
        }
    return out


def _derive_pre_decision_metrics(pre: Mapping[str, Any]) -> Dict[str, Any]:
    short = _safe_dict(pre.get("short_term"))
    mid = _safe_dict(pre.get("mid_term"))
    long = _safe_dict(pre.get("long_term"))
    short_pp = _safe_dict(short.get("participant_positioning"))
    mid_pp = _safe_dict(mid.get("participant_positioning"))
    long_ctx = _safe_dict(long.get("structural_context"))
    return {
        "short_term": {
            "liquidity_vacuum": bool(_safe_dict(short.get("structural_risks")).get("liquidity_vacuum") is True),
            "oi_trend": str(_safe_dict(short_pp.get("oi_dynamics")).get("oi_trend") or "unknown"),
            "delta_oi_pct": _safe_float(_safe_dict(short_pp.get("oi_delta")).get("delta_oi_pct"), default=0.0),
            "selected_interval": str(_safe_dict(short_pp.get("meta")).get("selected_interval") or "unknown"),
        },
        "mid_term": {
            "oi_trend": str(_safe_dict(mid_pp.get("oi_dynamics")).get("oi_trend") or "unknown"),
            "delta_oi_pct": _safe_float(_safe_dict(mid_pp.get("oi_delta")).get("delta_oi_pct"), default=0.0),
            "selected_interval": str(_safe_dict(mid_pp.get("meta")).get("selected_interval") or "unknown"),
        },
        "long_term": {
            "trend_maturity": str(long_ctx.get("trend_maturity") or "unknown"),
            "leverage_extreme": bool(long_ctx.get("leverage_extreme") is True),
            "crowding_zone": str(_safe_dict(long_ctx.get("crowding_percentile")).get("zone") or "unknown"),
        },
    }


def _is_core_structure_unavailable(raw_market_structure: Mapping[str, Any]) -> bool:
    # 关键结构都为空时视为不可用，避免下游把“空结构”误判为“稳定结构”。
    raw = _safe_dict(raw_market_structure)
    return (
        not _safe_dict(raw.get("orderbook"))
        and not _safe_dict(raw.get("open_interest"))
        and not _safe_dict(raw.get("horizons"))
        and not _safe_dict(raw.get("behavioral"))
    )


class FeatureService:
    """Feature Layer：消费底层结构输出并组装 raw_market_structure / feature snapshot。"""

    def __init__(
        self,
        *,
        orderbook_provider: OrderbookProvider,
        open_interest_provider: OpenInterestProvider,
        horizons_provider: HorizonsProvider,
        behavior_provider: BehaviorProvider,
        indicators_provider: IndicatorsProvider,
    ) -> None:
        self._assert_provider(orderbook_provider, "orderbook_provider", "get_orderbook")
        self._assert_provider(open_interest_provider, "open_interest_provider", "get_open_interest")
        self._assert_provider(horizons_provider, "horizons_provider", "get_horizons")
        self._assert_provider(behavior_provider, "behavior_provider", "get_behavior")
        self._assert_provider(indicators_provider, "indicators_provider", "get_indicators")
        self._orderbook_provider = orderbook_provider
        self._open_interest_provider = open_interest_provider
        self._horizons_provider = horizons_provider
        self._behavior_provider = behavior_provider
        self._indicators_provider = indicators_provider

    @classmethod
    def from_bundle(cls, bundle: ProviderBundle) -> "FeatureService":
        return cls(
            orderbook_provider=bundle.orderbook_provider,
            open_interest_provider=bundle.open_interest_provider,
            horizons_provider=bundle.horizons_provider,
            behavior_provider=bundle.behavior_provider,
            indicators_provider=bundle.indicators_provider,
        )

    @staticmethod
    def _assert_provider(provider: Any, provider_name: str, method_name: str) -> None:
        method = getattr(provider, method_name, None)
        if not callable(method):
            raise TypeError(f"{provider_name} must implement callable {method_name}()")

    async def _assemble_raw_market_structure(self, exchange: str, symbol: str) -> Dict[str, Any]:
        orderbook_out, open_interest_out, horizons_out, behavior_out = await asyncio.gather(
            self._orderbook_provider.get_orderbook(exchange, symbol),
            self._open_interest_provider.get_open_interest(exchange, symbol),
            self._horizons_provider.get_horizons(exchange, symbol),
            self._behavior_provider.get_behavior(exchange, symbol),
        )

        horizons = ["short_term", "mid_term", "long_term"]
        pre: Dict[str, Any] = {}
        for hz in horizons:
            if hz == "long_term":
                ctx = _build_long_term_structural_context(open_interest_out, horizons_out)
                pre[hz] = {
                    "structural_context": {k: v for k, v in ctx.items() if k != "confidence"},
                    "structural_weight": "veto_only",
                    "confidence": _safe_dict(ctx.get("confidence")),
                }
                continue

            cell: Dict[str, Any] = {
                "participant_positioning": _build_participant_positioning(open_interest_out, hz),
                "behavioral_intent": _build_behavioral_intent(behavior_out, hz),
                "structural_risks": _build_structural_risks(orderbook_out, horizons_out, hz),
            }
            if hz == "short_term":
                cell["micro_liquidity"] = _build_micro_liquidity(orderbook_out, include_snapshot=True)
            pre[hz] = cell

        return {
            "symbol": symbol,
            "candidate_horizons": horizons,
            "pre_decision_structure": pre,
            "horizons": dict(horizons_out or {}),
            "orderbook": dict(orderbook_out or {}),
            "open_interest": dict(open_interest_out or {}),
            "behavioral": dict(behavior_out or {}),
        }

    async def get_raw_structure(self, exchange: str, symbol: str) -> Dict[str, Any]:
        reset_degradation_state()
        exchange_norm = normalize_exchange(exchange)
        symbol_norm = normalize_symbol(symbol)
        raw_market_structure = await self._assemble_raw_market_structure(exchange_norm, symbol_norm)
        degraded_reasons = normalize_degraded_reasons(snapshot_degradation_reasons())
        normalized_raw = normalize_raw_market_structure(raw_market_structure, symbol=symbol_norm)
        if _is_core_structure_unavailable(normalized_raw):
            raise FeatureDataUnavailableError(
                exchange=exchange_norm,
                symbol=symbol_norm,
                degraded_reasons=degraded_reasons,
            )

        return {
            "exchange": exchange_norm,
            "symbol": symbol_norm,
            "raw_market_structure": normalized_raw,
            "degraded": bool(degraded_reasons),
            "degraded_reasons": degraded_reasons,
        }

    async def get_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        reset_degradation_state()
        exchange_norm = normalize_exchange(exchange)
        symbol_norm = normalize_symbol(symbol)
        raw_market_structure, indicators = await asyncio.gather(
            self._assemble_raw_market_structure(exchange_norm, symbol_norm),
            self._indicators_provider.get_indicators(exchange_norm, symbol_norm),
        )
        degraded_reasons = normalize_degraded_reasons(snapshot_degradation_reasons())
        pre = raw_market_structure.get("pre_decision_structure")
        horizons = raw_market_structure.get("horizons")
        orderbook = raw_market_structure.get("orderbook")
        open_interest = raw_market_structure.get("open_interest")
        behavioral = raw_market_structure.get("behavioral")
        features_payload = {
            "indicators": dict(indicators or {}),
            "derived_metrics": {
                "candidate_horizons": list(raw_market_structure.get("candidate_horizons") or []) if isinstance(raw_market_structure, dict) else [],
                "indicator_metrics": _derive_indicator_metrics(dict(indicators or {})),
                "horizon_metrics": _derive_horizon_metrics(_safe_dict(horizons)),
                "orderbook_metrics": _derive_orderbook_metrics(_safe_dict(orderbook)),
                "open_interest_metrics": _derive_open_interest_metrics(_safe_dict(open_interest)),
                "behavior_metrics": _derive_behavior_metrics(_safe_dict(behavioral)),
                "pre_decision_metrics": _derive_pre_decision_metrics(_safe_dict(pre)),
            },
            "structure_snapshot": {
                "pre_decision_structure": pre if isinstance(pre, dict) else {},
                "horizons": horizons if isinstance(horizons, dict) else {},
            },
        }
        normalized_raw = normalize_raw_market_structure(raw_market_structure, symbol=symbol_norm)
        if _is_core_structure_unavailable(normalized_raw):
            raise FeatureDataUnavailableError(
                exchange=exchange_norm,
                symbol=symbol_norm,
                degraded_reasons=degraded_reasons,
            )

        return {
            "exchange": exchange_norm,
            "symbol": symbol_norm,
            "degraded": bool(degraded_reasons),
            "degraded_reasons": degraded_reasons,
            "features": normalize_features_payload(features_payload),
        }
