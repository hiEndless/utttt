from typing import Any, Dict, List, Optional


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _stdev(xs: List[float]) -> float:
    if not xs or len(xs) < 2:
        return 0.0
    m = _mean(xs)
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return var ** 0.5


def _trend(delta: float, eps: float = 1e-5) -> str:
    if abs(delta) < eps:
        return "flat"
    return "up" if delta > 0 else "down"


def _trend_pct(pct: float, eps_pct: float = 0.01) -> str:
    """基于百分比变化判断趋势（默认 0.01% 内视为震荡）。"""
    if abs(pct) < eps_pct:
        return "flat"
    return "up" if pct > 0 else "down"


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _kline_close(k: Any) -> Optional[float]:
    """兼容 K 线数组结构与少量变体，提取 close。"""
    if isinstance(k, (list, tuple)) and len(k) >= 5:
        c = _safe_float(k[4], default=0.0)
        return None if c == 0.0 else c
    if isinstance(k, dict):
        for key in ("close", "c", "closePrice", "close_price"):
            if key in k:
                c = _safe_float(k.get(key), default=0.0)
                return None if c == 0.0 else c
    return None


def analyze_price_trends_from_klines(klines_by_interval: Dict[str, Any], intervals: List[str]) -> Dict[str, Any]:
    """从多周期 K 线计算各周期价格变化与趋势（供 horizon 聚合使用）。"""
    if not klines_by_interval:
        return {"price_change_pct": {}, "trends": {}, "latest_close": {}}

    changes: Dict[str, float] = {}
    trends: Dict[str, str] = {}
    latest_close: Dict[str, float] = {}

    for interval in intervals:
        klines = klines_by_interval.get(interval) or []
        if not isinstance(klines, list) or len(klines) < 2:
            continue

        prev = _kline_close(klines[-2])
        last = _kline_close(klines[-1])
        if prev is None or last is None or prev == 0:
            continue

        pct = (last - prev) / prev * 100.0
        changes[interval] = round(pct, 4)
        trends[interval] = _trend_pct(pct)
        latest_close[interval] = last

    return {"price_change_pct": changes, "trends": trends, "latest_close": latest_close}


def _stability(vol: float) -> str:
    if vol < 0.02:
        return "stable"
    if vol < 0.05:
        return "medium"
    return "volatile"


def analyze_funding(fr_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算资金费率的当前值、均值、变化与稳定性标签。"""
    if not fr_list:
        return {}

    last = fr_list[-20:]
    series = [float(x.get("fundingRate", 0.0)) for x in last]
    cur = series[-1]
    mean = _mean(series)
    vol = _stdev(series)
    delta = series[-1] - series[-2] if len(series) >= 2 else 0

    return {
        "current": cur,
        "mean": mean,
        "delta": delta,
        "volatility": vol,
        "trend": _trend(delta),
        "stability": _stability(vol),
        "bias": "bullish" if cur > 0 else ("bearish" if cur < 0 else "neutral"),
    }

