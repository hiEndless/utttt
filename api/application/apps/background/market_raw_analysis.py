import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

_d = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_d, "..", "..", "..", ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

try:
    from ...common.redis_client import redis_client
except ImportError:
    from api.application.common.redis_client import redis_client


PERIODS = ["5m", "15m", "30m", "1h", "2h", "4h", "1d"]
TYPES = [
    "globalLongShortAccountRatio",
    "takerLongShortRatio",
    "topLongShortPositionRatio",
    "topLongShortAccountRatio",
]

EXTRA_SIMPLE = {
    "24hr": "24hr",
    "fundingRate": "fundingRate",
}


def _init_result() -> Dict[str, Any]:
    base = {t: {p: [] for p in PERIODS} for t in TYPES}
    base["24hr"] = {}
    base["fundingRate"] = []
    return base


# -------------------------------------------------------------------------
# Redis Raw Reader
# -------------------------------------------------------------------------
async def read_market_raw(exchange: str, symbol: str, client: Optional[object] = None) -> Dict[str, Any]:
    cli = client or redis_client
    res = _init_result()

    cursor = 0
    pattern = f"market_raw:{exchange}:{symbol}:*"

    while True:
        cursor, keys = await cli.scan(cursor=cursor, match=pattern, count=1000)
        for key in keys:
            parts = key.split(":")

            if len(parts) == 5:
                interval, dtype = parts[3], parts[4]
            elif len(parts) == 4:
                interval, dtype = None, parts[3]
            else:
                continue

            raw = await cli.get(key)
            if not raw:
                continue

            try:
                data = json.loads(raw)
            except Exception:
                continue

            # ticker / fundingRate（无周期）
            if interval is None and dtype in EXTRA_SIMPLE:
                if dtype == "24hr" and isinstance(data, dict):
                    res["24hr"] = data
                elif dtype == "fundingRate":
                    if isinstance(data, list):
                        res["fundingRate"] = data
                    else:
                        res["fundingRate"] = [data]
                continue

            # 多空比类
            if dtype not in TYPES:
                continue

            mapped = "5m" if interval == "1m" else interval
            if mapped not in PERIODS:
                continue

            res[dtype][mapped] = data if isinstance(data, list) else [data]

        if cursor == 0:
            break

    return res


# -------------------------------------------------------------------------
# Utility
# -------------------------------------------------------------------------
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


def _strength(ratio: float) -> str:
    if ratio >= 1.2 or ratio <= 1 / 1.2:
        return "strong"
    if ratio >= 1.05 or ratio <= 1 / 1.05:
        return "medium"
    return "weak"


def _bias(ratio: float) -> str:
    if ratio > 1.05:
        return "long"
    if ratio < 0.95:
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
    return int(items[-1].get(key, 0))


# -------------------------------------------------------------------------
# Participant Structure Processing (核心)
# -------------------------------------------------------------------------
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


def _analyze_period(dtype: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not items:
        return {"current": {}, "stats": {}, "trend": {}, "labels": {}}

    cur = _current_for_type(dtype, items[-1])

    series = _series_ls(dtype, items[-10:])
    mean = _mean(series)
    vol = _stdev(series)
    delta = series[-1] - series[-2] if len(series) >= 2 else 0

    # Long/Short trend
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


# -------------------------------------------------------------------------
# Ticker 24h Analysis
# -------------------------------------------------------------------------
def analyze_ticker(tk: Dict[str, Any]) -> Dict[str, Any]:
    if not tk:
        return {}

    high = float(tk.get("highPrice"))
    low = float(tk.get("lowPrice"))

    quote_volume = float(tk.get("quoteVolume", 0))
    price_change_pct = float(tk.get("priceChangePercent"))

    trend = "up" if price_change_pct > 0 else ("down" if price_change_pct < 0 else "flat")

    vol_range = (high - low) / low if low else 0
    vol_label = "low" if vol_range < 0.01 else ("medium" if vol_range < 0.03 else "high")

    return {
        "price_change_pct_24h": round(price_change_pct, 4),
        "high_24h": high,
        "low_24h": low,
        "quote_volume_24h": quote_volume,
        "volatility_24h": vol_label,
        "trend_24h": trend,
    }


# -------------------------------------------------------------------------
# Funding Rate Analysis
# -------------------------------------------------------------------------
def analyze_funding(fr_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not fr_list:
        return {}

    # 最近 20 条
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


# -------------------------------------------------------------------------
# Final participant structure build
# -------------------------------------------------------------------------
def build_participant_structure(data: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    out = {
        "symbol": symbol,
        "generated_at": int(time.time() * 1000),
        "ticker": {},
        "funding_rate": {},
        "participant_structure": {},
        "summary": {},
    }

    ps = {}
    latest_ts = 0

    for dtype in TYPES:
        ps[dtype] = {}
        for p in PERIODS:
            items = data.get(dtype, {}).get(p, [])
            ps[dtype][p] = _analyze_period(dtype, items)
            latest_ts = max(latest_ts, _latest_ts(items))

    out["participant_structure"] = ps

    # ------------------------------
    # Add ticker
    # ------------------------------
    ticker_raw = data.get("24hr", {})
    out["ticker"] = analyze_ticker(ticker_raw)

    # ------------------------------
    # Add funding rate
    # ------------------------------
    fr_raw = data.get("fundingRate", [])
    out["funding_rate"] = analyze_funding(fr_raw)

    # Fix timestamp
    if fr_raw:
        latest_ts = max(latest_ts, _latest_ts(fr_raw, key="fundingTime"))
    out["generated_at"] = latest_ts or int(time.time() * 1000)

    # ------------------------------
    # Build summary
    # ------------------------------
    biases = []
    vols = []

    for dtype in TYPES:
        for p in PERIODS:
            cur = ps[dtype][p]["current"]
            stats = ps[dtype][p]["stats"]
            if cur and stats:
                biases.append(_bias(float(cur.get("ls_ratio", 1.0))))
                vols.append(stats.get("vol_ls_ratio", 0.0))

    long_cnt = biases.count("long")
    short_cnt = biases.count("short")
    total_cnt = len(biases) or 1

    avg_vol = _mean(vols) if vols else 0.0
    cross_bias = "long" if long_cnt > short_cnt else ("short" if short_cnt > long_cnt else "neutral")
    cross_stability = _stability(avg_vol)
    alignment_score = round(max(long_cnt, short_cnt) / total_cnt, 2)
    notes = f"跨周期加权判断为 {cross_bias}，一致性评分 {alignment_score}，结构稳定性 {cross_stability}。"
    notes += f" 平均波动 {round(avg_vol, 6)}。"

    out["summary"] = {
        "cross_period_bias": cross_bias,
        "cross_period_stability": cross_stability,
        "funding_bias": out["funding_rate"].get("bias", "neutral"),
        "funding_stability": out["funding_rate"].get("stability", "unknown"),
        "price_trend_24h": out["ticker"].get("trend_24h", "flat"),
        "market_context": _market_context(out),
        "alignment_score": alignment_score,
        "notes": notes,
    }

    return out


def _market_context(out: Dict[str, Any]) -> str:
    """Combine price trend + funding bias to infer general context."""
    price_t = out["ticker"].get("trend_24h", "flat")
    funding_b = out["funding_rate"].get("bias", "neutral")

    if price_t == "up" and funding_b == "bullish":
        return "strong_uptrend"
    if price_t == "down" and funding_b == "bearish":
        return "strong_downtrend"
    if funding_b == "bullish":
        return "bullish_sentiment"
    if funding_b == "bearish":
        return "bearish_sentiment"
    return "neutral"


# -------------------------------------------------------------------------
# Test run
# -------------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio

    raw = asyncio.run(read_market_raw("binance", "BTCUSDT"))
    result = build_participant_structure(raw, "BTCUSDT")
    print(json.dumps(result, ensure_ascii=False, indent=2))
