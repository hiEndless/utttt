from collections import Counter
from typing import Any, Dict, List, Optional, Tuple


def _safe_str(x: Any) -> str:
    return str(x) if x is not None else ""


def _normalize_trend(x: Any) -> str:
    v = _safe_str(x).lower()
    if v in {"bullish", "bearish", "neutral"}:
        return v
    if v in {"up", "uptrend"}:
        return "bullish"
    if v in {"down", "downtrend"}:
        return "bearish"
    if v in {"sideways", "range", "flat"}:
        return "neutral"
    return "unknown"


def _normalize_structure(x: Any) -> str:
    v = _safe_str(x).lower()
    if not v:
        return "unknown"
    return v


def _normalize_momentum(x: Any) -> str:
    v = _safe_str(x).lower()
    if v in {"strengthening", "weakening", "stable", "exhausted"}:
        return v
    return "unknown"


def _normalize_risk(x: Any) -> str:
    v = _safe_str(x).lower()
    if v in {"low", "medium", "high"}:
        return v
    return "unknown"


def _normalize_volatility(x: Any) -> str:
    v = _safe_str(x).lower()
    if v in {"low", "medium", "high"}:
        return v
    return "unknown"


def _normalize_proximity(x: Any) -> str:
    v = _safe_str(x).lower()
    if not v:
        return "unknown"
    if v.startswith("near_"):
        return v[len("near_") :]
    return v


def _weighted_majority(values: List[str], weights: List[float]) -> Tuple[str, float]:
    """加权多数投票，返回 (winner, agreement)。"""
    tally: Dict[str, float] = {}
    total = 0.0
    for v, w in zip(values, weights):
        if v in {"unknown", ""}:
            continue
        wt = float(w)
        total += wt
        tally[v] = tally.get(v, 0.0) + wt
    if total <= 0:
        return "unknown", 0.0
    winner, win_w = max(tally.items(), key=lambda kv: kv[1])
    return winner, round(win_w / total, 2)


def _risk_level(risk_state: str, volatility_state: str) -> str:
    """将 (risk_state, volatility_state) 映射为 risk_level。"""
    r_map = {"low": 0.0, "medium": 1.0, "high": 2.0}
    v_map = {"low": 0.0, "medium": 0.5, "high": 1.0}
    score = r_map.get(risk_state, 1.0) + v_map.get(volatility_state, 0.5)
    if score >= 2.7:
        return "high"
    if score >= 2.2:
        return "medium_high"
    if score >= 1.0:
        return "medium"
    return "low"


def _merge_level(values: List[str]) -> str:
    if not values:
        return "unknown"
    c = Counter([v for v in values if v not in {"unknown", ""}])
    return c.most_common(1)[0][0] if c else "unknown"


def aggregate_kline_background_by_horizon(
    kline_backgrounds: List[Dict[str, Any]],
    intervals: List[str],
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    w = weights or {}
    latest_by_interval: Dict[str, Dict[str, Any]] = {}
    for bg in kline_backgrounds or []:
        itv = bg.get("interval")
        if itv not in intervals:
            continue
        ts = int(bg.get("ts", 0) or 0)
        prev = latest_by_interval.get(itv)
        if not prev or ts >= int(prev.get("ts", 0) or 0):
            latest_by_interval[itv] = bg

    used_intervals = [itv for itv in intervals if itv in latest_by_interval]
    if not used_intervals:
        return {
            "directional_bias": "unknown",
            "trend_permission": False,
            "structure_state": "unknown",
            "momentum_state": "unknown",
            "risk_level": "unknown",
            "confidence": 0.0,
            "evidence_count": 0,
        }

    trends: List[str] = []
    momentums: List[str] = []
    structures: List[str] = []
    proximities: List[str] = []
    risks: List[str] = []
    vols: List[str] = []
    trend_weights: List[float] = []

    for itv in used_intervals:
        bg = latest_by_interval[itv] or {}
        env = bg.get("environment") or {}
        struct = bg.get("structure") or {}

        t = _normalize_trend(bg.get("trend") or env.get("market_trend"))
        m = _normalize_momentum(env.get("momentum_state"))
        s = _normalize_structure(struct.get("state"))
        p = _normalize_proximity(struct.get("key_level_proximity"))
        r = _normalize_risk(env.get("risk_state"))
        v = _normalize_volatility(env.get("volatility_state"))

        wt = float(w.get(itv, 1.0))
        trends.append(t)
        momentums.append(m)
        structures.append(s)
        proximities.append(p)
        risks.append(r)
        vols.append(v)
        trend_weights.append(wt)

    direction, agreement = _weighted_majority(trends, trend_weights)
    momentum, momentum_agree = _weighted_majority(momentums, trend_weights)
    structure = _merge_level(structures)
    proximity = _merge_level(proximities)

    risk_levels = [_risk_level(r, v) for r, v in zip(risks, vols)]
    risk_level = _merge_level(risk_levels)

    if direction in {"unknown"}:
        directional_bias = "unknown"
    elif agreement < 0.6:
        directional_bias = "mixed"
    else:
        directional_bias = direction

    if structure in {"consolidating", "range"}:
        if (
            directional_bias in {"bullish", "bearish"}
            and agreement >= 0.7
            and momentum in {"strengthening", "stable"}
        ):
            structure_state = "range_conflict"
        else:
            structure_state = "range_consolidation"
    else:
        structure_state = structure if structure != "unknown" else "unknown"

    if proximity != "unknown" and structure_state in {"range_consolidation", "range_conflict"}:
        structure_state = f"{structure_state}_near_{proximity}"

    if momentum_agree < 0.55 or momentum in {"unknown"}:
        momentum_state = "unstable"
    else:
        momentum_state = momentum

    in_range = structure_state.startswith("range_consolidation") or structure_state.startswith("range_conflict")

    if in_range and directional_bias in {"bullish", "bearish"}:
        directional_risk_skew = "upside" if directional_bias == "bullish" else "downside"
        directional_bias = "neutral"
    elif directional_bias == "neutral":
        directional_risk_skew = "balanced"
    elif directional_bias in {"bullish", "bearish"}:
        directional_risk_skew = "balanced"
    elif directional_bias == "mixed":
        directional_risk_skew = "unknown"
    else:
        directional_risk_skew = "unknown"

    if directional_bias == "neutral" and directional_risk_skew == "balanced":
        if direction == "bearish" and agreement >= 0.6:
            directional_risk_skew = "downside"
        elif direction == "bullish" and agreement >= 0.6:
            directional_risk_skew = "upside"

    if (
        directional_bias == "neutral"
        and momentum_state in {"weakening", "exhausted"}
        and directional_risk_skew == "balanced"
    ):
        directional_risk_skew = "downside"

    if directional_bias == "neutral" and risk_level in {"medium_high", "high"} and directional_risk_skew == "balanced":
        directional_risk_skew = "downside"

    trend_permission = (
        directional_bias in {"bullish", "bearish"}
        and agreement >= 0.75
        and momentum_state in {"strengthening", "stable"}
        and risk_level not in {"medium_high", "high"}
        and not in_range
    )

    confidence = round((agreement * 0.6 + momentum_agree * 0.4), 2)

    return {
        "directional_bias": directional_bias,
        "directional_risk_skew": directional_risk_skew,
        "trend_permission": bool(trend_permission),
        "structure_state": structure_state,
        "momentum_state": momentum_state,
        "risk_level": risk_level,
        "confidence": confidence,
        "evidence_count": len(used_intervals),
        "used_intervals": used_intervals,
    }

