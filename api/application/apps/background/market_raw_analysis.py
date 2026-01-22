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
    "ticker24hr": "ticker24hr",
    "fundingRate": "fundingRate",
}


def _init_result() -> Dict[str, Any]:
    base = {t: {p: [] for p in PERIODS} for t in TYPES}
    base["ticker24hr"] = {}
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
                if dtype == "ticker24hr" and isinstance(data, dict):
                    res["ticker24hr"] = data
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


def _zscore(val: float, mean: float, std: float) -> float:
    if std == 0:
        return 0.0
    return (val - mean) / std


def _safe_get_stat(stats: Dict[str, Any], key: str, field: str) -> float:
    """Helper to safely get nested stats."""
    return stats.get(key, {}).get(field, 0.0)


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

    # Analyze LS Ratio (Long/Short Ratio)
    # Using last 30 points for better stats
    series_ls = _series_ls(dtype, items[-30:])
    mean_ls = _mean(series_ls)
    vol_ls = _stdev(series_ls)
    delta_ls = series_ls[-1] - series_ls[-2] if len(series_ls) >= 2 else 0
    zscore_ls = _zscore(series_ls[-1], mean_ls, vol_ls)

    # Analyze Long Pct (Account Long %)
    if dtype == "takerLongShortRatio":
        # For taker, calculate from buy/sell vol
        series_lp = []
        for x in items[-30:]:
            bv = float(x.get("buyVol", 0) or 0)
            sv = float(x.get("sellVol", 0) or 0)
            tot = bv + sv
            series_lp.append(bv / tot if tot else 0)
    else:
        # For account ratios, use longAccount
        series_lp = [float(x.get("longAccount", 0)) for x in items[-30:]]

    mean_lp = _mean(series_lp)
    vol_lp = _stdev(series_lp)
    delta_lp = series_lp[-1] - series_lp[-2] if len(series_lp) >= 2 else 0
    zscore_lp = _zscore(series_lp[-1], mean_lp, vol_lp)

    # Long/Short trend
    if len(items) >= 2:
        prev = items[-2]
        prev_long = float(prev.get("longAccount", cur.get("long_pct", 0)))
        prev_short = float(prev.get("shortAccount", cur.get("short_pct", 0)))
    else:
        prev_long, prev_short = cur.get("long_pct", 0), cur.get("short_pct", 0)

    return {
        "current": cur,
        "stats": {
            "mean_ls_ratio": mean_ls,
            "delta_ls_ratio": delta_ls,
            "vol_ls_ratio": vol_ls,
            "ls_ratio": {
                "value": series_ls[-1] if series_ls else 0,
                "mean": mean_ls,
                "delta": delta_ls,
                "vol": vol_ls,
                "zscore": zscore_ls,
            },
            "long_pct": {
                "value": series_lp[-1] if series_lp else 0,
                "mean": mean_lp,
                "delta": delta_lp,
                "vol": vol_lp,
                "zscore": zscore_lp,
            },
        },
        "trend": {
            "ls_trend": _trend(delta_ls),
            "long_trend": _trend(cur.get("long_pct", 0) - prev_long),
            "short_trend": _trend(cur.get("short_pct", 0) - prev_short),
        },
    }


# -------------------------------------------------------------------------
# Ticker 24h Analysis
# -------------------------------------------------------------------------
def analyze_ticker(tk: Dict[str, Any]) -> Dict[str, Any]:
    if not tk:
        return {}

    price = float(tk.get("lastPrice", tk.get("close", 0)))
    open_p = float(tk.get("openPrice", price))
    high = float(tk.get("highPrice", price))
    low = float(tk.get("lowPrice", price))

    quote_volume = float(tk.get("quoteVolume", 0))
    price_change_pct = (price - open_p) / open_p if open_p else 0

    trend = "up" if price_change_pct > 0 else ("down" if price_change_pct < 0 else "flat")

    vol_range = (high - low) / low if low else 0
    vol_label = "low" if vol_range < 0.01 else ("medium" if vol_range < 0.03 else "high")

    return {
        "price": price,
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
    }

    ps = {}
    latest_ts = 0

    for dtype in TYPES:
        ps[dtype] = {}
        for p in PERIODS:
            items = data.get(dtype, {}).get(p, [])
            ps[dtype][p] = _analyze_period(dtype, items)
            latest_ts = max(latest_ts, _latest_ts(items))

    # ------------------------------
    # Detailed Trend Analysis (For all 5 sources)
    # ------------------------------
    trends = {}

    # Helper to build analysis for standard types
    def build_type_analysis(type_name: str, metric_key: str):
        if type_name not in ps:
            return None
        
        # Get base value from 5m (most sensitive)
        base_data = ps[type_name].get("5m", {})
        if not base_data or not base_data.get("current"):
            # Try to find any available period
            for p in PERIODS:
                if ps[type_name].get(p, {}).get("current"):
                    base_data = ps[type_name][p]
                    break
        
        if not base_data:
            return None

        # Determine current value based on metric_key
        # metric_key is usually 'ls_ratio' or 'long_pct'
        # In 'current', keys are 'ls_ratio', 'long_pct', 'short_pct'
        current_val = base_data["current"].get(metric_key, 0)

        deltas = {}
        zscores = {}

        for p in PERIODS:
            p_stats = ps[type_name].get(p, {}).get("stats", {})
            # stats structure: { 'ls_ratio': {value, delta, zscore}, 'long_pct': {...} }
            stat_obj = p_stats.get(metric_key, {})
            if stat_obj:
                deltas[p] = round(stat_obj.get("delta", 0), 4)
                zscores[p] = round(stat_obj.get("zscore", 0), 2)
        
        return {
            "value": round(float(current_val), 4),
            "delta": deltas,
            "zscore": zscores
        }

    # 1. Global Account Ratio (Focus on long_pct)
    trends["account_long_ratio"] = build_type_analysis("globalLongShortAccountRatio", "long_pct")

    # 2. Taker Buy/Sell Ratio (Focus on ls_ratio)
    trends["taker_buy_sell_ratio"] = build_type_analysis("takerLongShortRatio", "ls_ratio")

    # 3. Top Position Ratio (Focus on ls_ratio)
    trends["top_position_ratio"] = build_type_analysis("topLongShortPositionRatio", "ls_ratio")

    # 4. Top Account Ratio (Focus on ls_ratio)
    trends["top_account_ratio"] = build_type_analysis("topLongShortAccountRatio", "ls_ratio")

    # 5. Funding Rate (Special handling)
    fr_raw = data.get("fundingRate", [])
    if fr_raw:
        # Re-calculate stats for funding rate to match structure
        # Funding rate is a single series, no periods. 
        # We can map 'last' change as delta, and window zscore.
        fr_series = [float(x.get("fundingRate", 0.0)) for x in fr_raw[-30:]]
        if fr_series:
            fr_cur = fr_series[-1]
            fr_mean = _mean(fr_series)
            fr_vol = _stdev(fr_series)
            fr_delta = fr_series[-1] - fr_series[-2] if len(fr_series) >= 2 else 0
            fr_zscore = _zscore(fr_cur, fr_mean, fr_vol)
            
            trends["funding_rate"] = {
                "value": round(fr_cur, 6),
                "delta": {"last_step": round(fr_delta, 6)},
                "zscore": {"window_30": round(fr_zscore, 2)}
            }
        else:
             trends["funding_rate"] = None
    else:
        trends["funding_rate"] = None

    out["trend_analysis"] = trends

    # ------------------------------
    # Add ticker
    # ------------------------------
    ticker_raw = data.get("ticker24hr", {})
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

    return out


# -------------------------------------------------------------------------
# Test run
# -------------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio

    raw = asyncio.run(read_market_raw("binance", "BTCUSDT"))
    result = build_participant_structure(raw, "BTCUSDT")
    print(json.dumps(result, ensure_ascii=False, indent=2))
