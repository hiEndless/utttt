import json
import os
import sys
import time
from typing import Any, Dict, List, Optional
from statistics import median

_d = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_d, "..", "..", "..", ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)
try:
    from ...common.redis_client import redis_client
except ImportError:
    from api.application.common.redis_client import redis_client

# --- CONFIG ---
PERIODS = ["5m", "15m", "30m", "1h", "2h", "4h", "1d"]
TYPES = [
    "globalLongShortAccountRatio",
    "takerLongShortRatio",
    "topLongShortPositionRatio",
    "topLongShortAccountRatio",
]
EXTRA_SIMPLE = {
    "ticker24hr": "ticker24hr",
    "fundingRate": "fundingRate",
}

# how many recent points to use for series-based stats (configurable)
DEFAULT_WINDOW = 50

# weights for summary: you can tune these
TYPE_WEIGHTS = {
    "globalLongShortAccountRatio": 2.0,
    "topLongShortPositionRatio": 2.0,
    "topLongShortAccountRatio": 2.0,
    "takerLongShortRatio": 1.0,
}
# period weights (longer period => more weight)
PERIOD_WEIGHTS = {"5m": 1.0, "15m": 1.2, "30m": 1.4, "1h": 1.6, "2h": 1.8, "4h": 2.0, "1d": 2.5}


def _init_result() -> Dict[str, Any]:
    base = {t: {p: [] for p in PERIODS} for t in TYPES}
    base["ticker24hr"] = {}
    base["fundingRate"] = []
    return base


def _to_float(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _stdev(xs: List[float]) -> float:
    if not xs or len(xs) < 2:
        return 0.0
    m = _mean(xs)
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return var ** 0.5


def _trend(delta: float, tol: float = 1e-3) -> str:
    if abs(delta) <= tol:
        return "flat"
    return "up" if delta > 0 else "down"


def _strength_from_ratio(ratio: float) -> str:
    """
    strength classification by deviation from 1.0 (neutral).
    Use directional bias separately.
    """
    diff = abs(ratio - 1.0)
    if diff >= 0.2:
        return "strong"
    if diff >= 0.05:
        return "medium"
    return "weak"


def _bias_from_long_short(long_pct: float, short_pct: float, tol: float = 0.05) -> str:
    diff = long_pct - short_pct
    if diff > tol:
        return "long"
    if diff < -tol:
        return "short"
    return "neutral"


def _stability(vol: float) -> str:
    if vol < 0.02:
        return "stable"
    if vol < 0.05:
        return "medium"
    return "volatile"


def _latest_ts(items: List[Dict[str, Any]], key: str = "timestamp") -> int:
    if not items:
        return 0
    try:
        return int(items[-1].get(key, 0) or 0)
    except Exception:
        return 0


def _normalize_long_short(lp: float, sp: float) -> (float, float):
    total = lp + sp
    if total <= 0:
        return (0.0, 0.0)
    return (lp / total, sp / total)


def _current_for_type(dtype: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize various source schemas to unified current fields and timestamp.
    """
    # taker: buyVol/sellVol/buySellRatio
    if dtype == "takerLongShortRatio":
        bv = _to_float(entry.get("buyVol", 0))
        sv = _to_float(entry.get("sellVol", 0))
        total = bv + sv
        lp = (bv / total) if total > 0 else 0.0
        sp = (sv / total) if total > 0 else 0.0
        ratio = _to_float(entry.get("buySellRatio", 0)) or (lp / sp if sp > 0 else (lp * 10 if lp > 0 else 0.0))
        ts = int(entry.get("timestamp") or entry.get("time") or entry.get("ts") or 0)
        return {"long_pct": lp, "short_pct": sp, "ls_ratio": ratio, "timestamp": ts}
    # default: longAccount/shortAccount/longShortRatio
    lp = _to_float(entry.get("longAccount", 0))
    sp = _to_float(entry.get("shortAccount", 0))
    lp, sp = _normalize_long_short(lp, sp)
    ratio = _to_float(entry.get("longShortRatio", 0)) or (lp / sp if sp > 0 else (lp * 10 if lp > 0 else 0.0))
    ts = int(entry.get("timestamp") or entry.get("time") or entry.get("ts") or 0)
    return {"long_pct": lp, "short_pct": sp, "ls_ratio": ratio, "timestamp": ts}


def _series_ls(dtype: str, items: List[Dict[str, Any]]) -> List[float]:
    if not items:
        return []
    if dtype == "takerLongShortRatio":
        return [_to_float(x.get("buySellRatio", 0) or x.get("ls_ratio", 0)) for x in items]
    return [_to_float(x.get("longShortRatio", 0) or x.get("ls_ratio", 0)) for x in items]


def _analyze_period(dtype: str, items: List[Dict[str, Any]], window: int = DEFAULT_WINDOW) -> Dict[str, Any]:
    """
    Produce a period-level analysis dict:
      - current: current normalized values + timestamp
      - stats: mean, min, max, count, delta, vol
      - trend: ls_trend, long_trend, short_trend
      - labels: bias, stability, strength
    """
    if not items:
        return {"current": {}, "stats": {}, "trend": {}, "labels": {}}
    cur = _current_for_type(dtype, items[-1])
    window_items = items[-min(len(items), window):]
    ls_series = _series_ls(dtype, window_items)
    # stats
    mean_val = _mean(ls_series) if ls_series else 0.0
    min_val = min(ls_series) if ls_series else 0.0
    max_val = max(ls_series) if ls_series else 0.0
    count = len(ls_series)
    vol = _stdev(ls_series)
    med = median(ls_series) if ls_series else 0.0
    # delta: latest - previous
    delta = (ls_series[-1] - ls_series[-2]) if len(ls_series) >= 2 else 0.0
    # previous long/short for trend
    if len(items) >= 2:
        prev = _current_for_type(dtype, items[-2])
        prev_long = prev.get("long_pct", 0.0)
        prev_short = prev.get("short_pct", 0.0)
    else:
        prev_long = cur.get("long_pct", 0.0)
        prev_short = cur.get("short_pct", 0.0)
    ls_tr = _trend(delta)
    long_tr = _trend(cur.get("long_pct", 0.0) - prev_long)
    short_tr = _trend(cur.get("short_pct", 0.0) - prev_short)
    bias = _bias_from_long_short(cur.get("long_pct", 0.0), cur.get("short_pct", 0.0))
    strength = _strength_from_ratio(cur.get("ls_ratio", 1.0))
    stability = _stability(vol)
    return {
        "current": cur,
        "stats": {
            "mean_ls_ratio": mean_val,
            "min_ls_ratio": min_val,
            "max_ls_ratio": max_val,
            "median_ls_ratio": med,
            "count": count,
            "delta_ls_ratio": delta,
            "vol_ls_ratio": vol,
        },
        "trend": {"ls_trend": ls_tr, "long_trend": long_tr, "short_trend": short_tr},
        "labels": {"bias": bias, "stability": stability, "strength": strength},
    }


def _compute_summary(ps: Dict[str, Any]) -> Dict[str, Any]:
    """
    ps: participant_structure (type -> period -> analysis)
    compute cross_period bias, stability and alignment_score using TYPE_WEIGHTS & PERIOD_WEIGHTS
    """
    weighted_long = 0.0
    weighted_short = 0.0
    weighted_neutral = 0.0
    weight_total = 0.0
    vol_list = []
    # accumulate per (type, period)
    for dtype, periods in ps.items():
        tw = TYPE_WEIGHTS.get(dtype, 1.0)
        for p, analysis in periods.items():
            pw = PERIOD_WEIGHTS.get(p, 1.0)
            w = tw * pw
            labels = analysis.get("labels", {})
            bias = labels.get("bias")
            stats = analysis.get("stats", {})
            vol = stats.get("vol_ls_ratio", 0.0) or 0.0
            vol_list.append(float(vol))
            if bias == "long":
                weighted_long += w
            elif bias == "short":
                weighted_short += w
            else:
                weighted_neutral += w
            weight_total += w
    if weight_total <= 0:
        alignment_score = 0.0
    else:
        dominant = max(weighted_long, weighted_short, weighted_neutral)
        alignment_score = round(dominant / weight_total, 2)
    # cross_period_bias
    if weighted_long > weighted_short and weighted_long > weighted_neutral:
        cross_bias = "long"
    elif weighted_short > weighted_long and weighted_short > weighted_neutral:
        cross_bias = "short"
    else:
        cross_bias = "neutral"
    avg_vol = _mean(vol_list) if vol_list else 0.0
    cross_stability = _stability(avg_vol)
    # notes: generate controlled summary
    notes = f"跨周期加权判断为 {cross_bias}，一致性评分 {alignment_score}，结构稳定性 {cross_stability}。"
    # provide few supporting numbers
    notes += f" 平均波动 {round(avg_vol, 6)}。"
    return {
        "cross_period_bias": cross_bias,
        "cross_period_stability": cross_stability,
        "alignment_score": alignment_score,
        "notes": notes,
    }


def build_participant_structure(data: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "symbol": symbol,
        "generated_at": int(time.time() * 1000),
        "participant_structure": {},
        "summary": {},
    }
    latest_ts = 0
    ps: Dict[str, Any] = {}
    for dtype in TYPES:
        per: Dict[str, Any] = {}
        for p in PERIODS:
            items = data.get(dtype, {}).get(p, []) or []
            # ensure items sorted by timestamp ascending
            try:
                items_sorted = sorted(items, key=lambda x: int(x.get("timestamp") or x.get("time") or x.get("ts") or 0))
            except Exception:
                items_sorted = items
            per[p] = _analyze_period(dtype, items_sorted, window=DEFAULT_WINDOW)
            latest_ts = max(latest_ts, _latest_ts(items_sorted))
        ps[dtype] = per
    out["participant_structure"] = ps
    fr = data.get("fundingRate", [])
    if fr:
        latest_ts = max(latest_ts, _latest_ts(fr, key="fundingTime"))
    out["generated_at"] = latest_ts or int(time.time() * 1000)
    out["summary"] = _compute_summary(ps)
    return out


async def read_market_raw(exchange: str, symbol: str, client: Optional[object] = None) -> Dict[str, Any]:
    """
    Read keys like:
      market_raw:{exchange}:{symbol}:{interval}:{dtype}
      market_raw:{exchange}:{symbol}:{dtype}
    More robust parsing: last segment is dtype, second-last if in PERIODS (or '1m') is interval.
    Values expected to be JSON str: either a dict or a list.
    """
    cli = client or redis_client
    res = _init_result()
    cursor = 0
    pattern = f"market_raw:{exchange}:{symbol}:*"
    while True:
        cursor, keys = await cli.scan(cursor=cursor, match=pattern, count=1000)
        for key in keys:
            # key may be bytes depending on client
            if isinstance(key, bytes):
                key_s = key.decode()
            else:
                key_s = str(key)
            parts = key_s.split(":")
            if len(parts) < 4:
                continue
            dtype = parts[-1]
            second_last = parts[-2] if len(parts) >= 2 else None
            interval = None
            if second_last in PERIODS or second_last == "1m":
                interval = second_last
            # read value
            val = await cli.get(key)
            if not val:
                continue
            try:
                if isinstance(val, (bytes, bytearray)):
                    s = val.decode()
                else:
                    s = str(val)
                data = json.loads(s)
            except Exception:
                continue
            # extra simple types
            if interval is None and dtype in EXTRA_SIMPLE:
                target = EXTRA_SIMPLE[dtype]
                if target == "ticker24hr":
                    res[target] = data if isinstance(data, dict) else {}
                elif target == "fundingRate":
                    res[target] = data if isinstance(data, list) else [data]
                continue
            # only care about configured types
            if dtype not in TYPES:
                continue
            mapped_interval = "5m" if interval == "1m" else interval
            if mapped_interval not in PERIODS:
                continue
            # normalize to list
            if isinstance(data, list):
                arr = data
            else:
                arr = [data]
            res[dtype][mapped_interval] = arr
        if cursor == 0:
            break
    return res


# ----------------- offline utilities for analysis / main -----------------
if __name__ == "__main__":
    import asyncio

    # demo run
    raw = asyncio.run(read_market_raw(exchange="binance", symbol="BTCUSDT"))
    analyzed = build_participant_structure(raw, "BTCUSDT")
    print(json.dumps(analyzed, ensure_ascii=False, indent=2))
