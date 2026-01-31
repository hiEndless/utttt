from typing import Any, Dict, List


def _trend(delta: float, eps: float = 1e-5) -> str:
    """基于数值变化判断趋势：上涨/下跌/震荡。"""
    if abs(delta) < eps:
        return "flat"
    return "up" if delta > 0 else "down"


def _strength(ratio: float) -> str:
    """基于多空比绝对偏离判断强弱。"""
    if ratio >= 1.2 or ratio <= 1 / 1.2:
        return "strong"
    if ratio >= 1.05 or ratio <= 1 / 1.05:
        return "medium"
    return "weak"


def _bias(ratio: float) -> str:
    """基于多空比判断倾向：long/short/neutral。"""
    if ratio > 1.05:
        return "long"
    if ratio < 0.95:
        return "short"
    return "neutral"


def _stability(vol: float) -> str:
    """基于波动度判断稳定性标签。"""
    if vol < 0.02:
        return "stable"
    if vol < 0.05:
        return "medium"
    return "volatile"


def _current_for_type(dtype: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize current data for each type."""
    if dtype == "takerLongShortRatio":
        bv = float(entry.get("buyVol", 0) or 0)
        sv = float(entry.get("sellVol", 0) or 0)
        tot = bv + sv
        lp = bv / tot if tot else 0
        sp = sv / tot if tot else 0
        ratio = float(entry.get("buySellRatio", 1.0))
        return {"long_pct": lp, "short_pct": sp, "ls_ratio": ratio}

    lp = float(entry.get("longAccount", 0))
    sp = float(entry.get("shortAccount", 0))
    ratio = float(entry.get("longShortRatio", 1.0))
    return {"long_pct": lp, "short_pct": sp, "ls_ratio": ratio}


def _series_ls(dtype: str, items: List[Dict[str, Any]]) -> List[float]:
    if dtype == "takerLongShortRatio":
        return [float(x.get("buySellRatio", 1.0)) for x in items]
    return [float(x.get("longShortRatio", 1.0)) for x in items]


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _stdev(xs: List[float]) -> float:
    if not xs or len(xs) < 2:
        return 0.0
    m = _mean(xs)
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return var**0.5


def _analyze_period(dtype: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not items:
        return {"current": {}, "stats": {}, "trend": {}, "labels": {}}

    cur = _current_for_type(dtype, items[-1])

    series = _series_ls(dtype, items[-10:])
    mean = _mean(series)
    vol = _stdev(series)
    delta = series[-1] - series[-2] if len(series) >= 2 else 0

    if len(items) >= 2:
        prev = items[-2]
        prev_long = float(prev.get("longAccount", cur["long_pct"]))
        prev_short = float(prev.get("shortAccount", cur["short_pct"]))
    else:
        prev_long, prev_short = cur["long_pct"], cur["short_pct"]

    return {
        "current": cur,
        "stats": {
            "mean_ls_ratio": mean,
            "delta_ls_ratio": delta,
            "vol_ls_ratio": vol,
        },
        "trend": {
            "ls_trend": _trend(delta),
            "long_trend": _trend(cur["long_pct"] - prev_long),
            "short_trend": _trend(cur["short_pct"] - prev_short),
        },
        "labels": {
            "bias": _bias(cur["ls_ratio"]),
            "strength": _strength(cur["ls_ratio"]),
            "stability": _stability(vol),
        },
    }

