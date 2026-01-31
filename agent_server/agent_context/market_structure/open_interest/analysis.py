from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

TAG_DELTA_PCT_THRESHOLD = 0.002
ACCEL_EPS = 1e-4
STRUCTURAL_WEIGHT_INTERVALS = {"4h", "6h", "12h", "1d"}


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(float(x))
    except Exception:
        return default


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _stdev(xs: List[float]) -> float:
    if not xs or len(xs) < 2:
        return 0.0
    m = _mean(xs)
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return var**0.5


def _trend(delta: float, eps: float = 1e-12) -> str:
    if abs(delta) < eps:
        return "flat"
    return "up" if delta > 0 else "down"


def _extract_oi_points(items: Any) -> List[Tuple[int, float, float]]:
    if not isinstance(items, list):
        return []

    out: List[Tuple[int, float, float]] = []
    for obj in items:
        if not isinstance(obj, Mapping):
            continue
        ts = _safe_int(obj.get("timestamp") or obj.get("time") or obj.get("ts") or 0, default=0)
        oi = _safe_float(obj.get("sumOpenInterest") or obj.get("openInterest") or obj.get("oi") or 0.0, default=0.0)
        oiv = _safe_float(
            obj.get("sumOpenInterestValue") or obj.get("openInterestValue") or obj.get("oiValue") or 0.0,
            default=0.0,
        )
        if ts <= 0 or oi <= 0:
            continue
        out.append((ts, oi, oiv))

    out.sort(key=lambda x: x[0])
    dedup: List[Tuple[int, float, float]] = []
    last_ts = -1
    for ts, oi, oiv in out:
        if ts == last_ts:
            if dedup:
                dedup[-1] = (ts, oi, oiv)
            else:
                dedup.append((ts, oi, oiv))
        else:
            dedup.append((ts, oi, oiv))
        last_ts = ts
    return dedup


def _interval_to_horizon(interval: str) -> str:
    if interval in ("5m", "15m", "30m", "1h"):
        return "short_term"
    if interval in ("2h", "4h", "6h", "12h"):
        return "mid_term"
    return "long_term"


def _pick_agg_trade_mode(behavioral: Optional[Dict[str, Any]], interval: str) -> str:
    if not behavioral or not isinstance(behavioral, dict):
        return "unknown"
    hz = _interval_to_horizon(interval)
    bs = (behavioral.get("behavioral_structure") or {}).get(hz) or {}
    summary = bs.get("summary") or {}
    if isinstance(summary, dict):
        mm = summary.get("market_mode")
        return str(mm) if mm else "unknown"
    return "unknown"


def _velocity_label(speed: float, hist_speeds: List[float]) -> str:
    if speed <= 0:
        return "low"
    m = _mean(hist_speeds) if hist_speeds else 0.0
    sd = _stdev(hist_speeds) if hist_speeds else 0.0
    if speed >= m + sd and speed >= 0.003:
        return "high"
    if speed >= max(0.001, m):
        return "medium"
    return "low"


def _acceleration_label(last_delta_pct: float, prev_delta_pct: float) -> str:
    if abs(last_delta_pct) < 1e-12:
        return "flat"

    accel = float(last_delta_pct - prev_delta_pct)
    if abs(accel) < float(ACCEL_EPS):
        return "flat"

    if last_delta_pct > 0:
        return "accelerating_up" if accel > 0 else "decelerating_up"
    return "accelerating_down" if accel < 0 else "decelerating_down"


def _dominant_group(interval: str) -> str:
    hz = _interval_to_horizon(interval)
    if hz == "short_term":
        return "short_term_traders"
    if hz == "mid_term":
        return "mid_term_participants"
    return "long_term_holders"


def _humanize_tags(interval: str, base_tags: List[str]) -> List[str]:
    group = _dominant_group(interval)
    out: List[str] = []
    if "deleveraging" in base_tags:
        out.append(f"{group}_reducing_leverage")
    if "leverage_building" in base_tags:
        out.append(f"{group}_increasing_leverage")
    if "hedge_building_possible" in base_tags:
        out.append(f"{group}_building_hedge")
    if "directional_building" in base_tags:
        out.append(f"{group}_directional_building")
    if "passive_leverage_build" in base_tags:
        out.append(f"{group}_passive_leverage_build")
    return out


def _participant_inference(
    interval: str,
    human_tags: List[str],
    delta_oi_pct: float,
    velocity: str,
) -> Optional[Dict[str, Any]]:
    if not human_tags:
        return None

    group = _dominant_group(interval)
    behavior = "unknown"
    if any(t.endswith("_building_hedge") for t in human_tags):
        behavior = "hedging"
    elif any(t.endswith("_reducing_leverage") for t in human_tags):
        behavior = "reducing_leverage"
    elif any(t.endswith("_directional_building") for t in human_tags):
        behavior = "directional_building"
    elif any(t.endswith("_passive_leverage_build") for t in human_tags):
        behavior = "passive_building"
    elif any(t.endswith("_increasing_leverage") for t in human_tags):
        behavior = "increasing_leverage"

    abs_delta = abs(float(delta_oi_pct))
    if abs_delta >= 0.01 and velocity == "high":
        confidence = "high"
    elif abs_delta >= 0.004 and velocity in ("medium", "high"):
        confidence = "medium"
    else:
        confidence = "low"

    positioning_mode = _positioning_mode(behavior, abs_delta, velocity)

    return {
        "dominant_group": group,
        "behavior": behavior,
        "positioning_mode": positioning_mode,
        "confidence": confidence,
    }


def _positioning_mode(behavior: str, abs_delta_pct: float, velocity: str) -> str:
    if behavior == "reducing_leverage":
        return "risk_off"
    if behavior == "directional_building":
        return "risk_on"
    if behavior == "increasing_leverage":
        return "risk_on" if abs_delta_pct >= 0.004 and velocity in ("medium", "high") else "neutral"
    if behavior in ("hedging", "passive_building"):
        return "neutral"
    return "unclear"


def _structural_weight(interval: str) -> str:
    return "high" if str(interval) in STRUCTURAL_WEIGHT_INTERVALS else "low"


def _build_interpretation(
    oi_trend: str,
    delta_oi_pct: float,
    velocity: str,
    price_trend: str,
    taker_bias: str,
) -> Tuple[List[str], List[str]]:
    tags: List[str] = []
    risks: List[str] = []

    if delta_oi_pct >= 0.004:
        tags.append("leverage_building")
    elif delta_oi_pct <= -0.004:
        tags.append("deleveraging")

    if oi_trend == "up" and price_trend in ("up", "down"):
        if price_trend == "up" and taker_bias == "long":
            tags.extend(["trend_supported", "directional_building"])
        elif price_trend == "down" and taker_bias == "short":
            tags.extend(["trend_supported", "directional_building"])
        elif taker_bias in ("long", "short") and (
            (price_trend == "up" and taker_bias == "short") or (price_trend == "down" and taker_bias == "long")
        ):
            tags.append("hedge_building_possible")
            risks.append("leverage_price_conflict")

    if oi_trend == "up" and price_trend == "flat":
        tags.append("passive_leverage_build")
        if velocity in ("medium", "high"):
            risks.append("fragile_leverage_build")

    if oi_trend == "down" and velocity == "high":
        risks.append("possible_liquidation_or_unwind")

    if not risks and oi_trend in ("flat", "up") and velocity in ("low", "medium"):
        tags.append("no_liquidation_signal")

    tags = sorted(set([t for t in tags if t]))
    risks = sorted(set([r for r in risks if r]))
    return tags, risks


def analyze_open_interest_hist(
    open_interest_hist_by_interval: Mapping[str, Any],
    price_interval: Mapping[str, Any],
    taker_ratio_interval: Mapping[str, Any],
    ticker24hr: Optional[Mapping[str, Any]] = None,
    behavioral: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    price_trends = (price_interval or {}).get("trends") if isinstance(price_interval, Mapping) else {}
    quote_volume_24h = _safe_float((ticker24hr or {}).get("quoteVolume") or 0.0, default=0.0)

    for interval, raw_items in (open_interest_hist_by_interval or {}).items():
        points = _extract_oi_points(raw_items)
        if not points:
            out[str(interval)] = {
                "state": {},
                "delta": {},
                "dynamics": {},
                "coupling": {},
                "interpretation_tags": [],
                "risk_flags": [],
            }
            continue

        ts, oi, oiv = points[-1]
        prev_oi = points[-2][1] if len(points) >= 2 else oi
        delta_oi = float(oi - prev_oi)
        delta_oi_pct = float(delta_oi / prev_oi) if prev_oi > 0 else 0.0

        deltas_pct: List[float] = []
        for i in range(max(1, len(points) - 10), len(points)):
            cur = points[i][1]
            prev = points[i - 1][1]
            if prev > 0:
                deltas_pct.append((cur - prev) / prev)
        speed_hist = [abs(x) for x in deltas_pct] if deltas_pct else []
        speed_cur = abs(delta_oi_pct)
        velocity = _velocity_label(speed_cur, speed_hist)

        last_delta_pct = float(deltas_pct[-1]) if deltas_pct else float(delta_oi_pct)
        prev_delta_pct = float(deltas_pct[-2]) if len(deltas_pct) >= 2 else float(last_delta_pct)
        acceleration = _acceleration_label(last_delta_pct, prev_delta_pct)

        oi_trend = _trend(points[-1][1] - points[-2][1]) if len(points) >= 2 else "flat"

        price_trend = "unknown"
        if isinstance(price_trends, Mapping):
            price_trend = str(price_trends.get(interval) or "unknown")

        taker_bias = "unknown"
        tctx = taker_ratio_interval.get(interval) if isinstance(taker_ratio_interval, Mapping) else None
        if isinstance(tctx, Mapping):
            labels = tctx.get("labels") or {}
            if isinstance(labels, Mapping):
                taker_bias = str(labels.get("bias") or "unknown")

        agg_trade_mode = _pick_agg_trade_mode(behavioral, str(interval))

        base_tags, base_risks = _build_interpretation(
            oi_trend=oi_trend,
            delta_oi_pct=float(delta_oi_pct),
            velocity=str(velocity),
            price_trend=str(price_trend),
            taker_bias=str(taker_bias),
        )

        allow_tags = abs(float(delta_oi_pct)) >= float(TAG_DELTA_PCT_THRESHOLD) and str(velocity) in ("medium", "high")
        human_tags = _humanize_tags(str(interval), base_tags) if allow_tags else []
        risk_flags = sorted(set([r for r in (base_risks if allow_tags else []) if r]))
        participant_inference = _participant_inference(str(interval), human_tags, float(delta_oi_pct), str(velocity)) if allow_tags else None

        oi_to_quote_volume_ratio = float(oiv / quote_volume_24h) if quote_volume_24h > 0 and oiv > 0 else 0.0

        coupling: Dict[str, Any] = {
            "price_trend": str(price_trend),
            "taker_bias": str(taker_bias),
        }
        if str(agg_trade_mode) and str(agg_trade_mode) != "unknown":
            coupling["agg_trade_mode"] = str(agg_trade_mode)

        out[str(interval)] = {
            "state": {
                "open_interest": float(oi),
                "open_interest_value": float(oiv),
                "oi_to_quote_volume_ratio": round(float(oi_to_quote_volume_ratio), 6),
            },
            "delta": {
                "delta_oi": round(delta_oi, 6),
                "delta_oi_pct": round(float(delta_oi_pct), 6),
            },
            "dynamics": {
                "oi_trend": str(oi_trend),
                "oi_velocity": str(velocity),
                "oi_acceleration": str(acceleration),
            },
            "coupling": coupling,
            "interpretation_tags": human_tags,
            "risk_flags": risk_flags,
            "meta": {"latest_ts": int(ts), "points": int(len(points)), "structural_weight": _structural_weight(str(interval))},
        }
        if participant_inference:
            out[str(interval)]["participant_inference"] = participant_inference

    return out
