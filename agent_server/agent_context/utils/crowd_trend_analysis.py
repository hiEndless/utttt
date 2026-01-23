import time
from typing import Any, Dict, List, Optional
try:
    from ...utils.redis_client import get_redis_client
except ImportError:
    from agent_server.utils.redis_client import get_redis_client


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


def _latest_ts(items: List[Dict[str, Any]], key: str = "timestamp") -> int:
    if not items:
        return 0
    return int(items[-1].get(key, 0))


def _init_result() -> Dict[str, Any]:
    base = {t: {p: [] for p in PERIODS} for t in TYPES}
    base["24hr"] = {}
    base["fundingRate"] = []
    return base


# -------------------------------------------------------------------------
# Participant Structure Processing
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


def analyze_period(dtype: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
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

    return {
        "current": cur,
        "ls_ratio_stats": {
            "value": series_ls[-1] if series_ls else 0,
            "mean": mean_ls,
            "delta": delta_ls,
            "vol": vol_ls,
            "zscore": zscore_ls,
        },
        "long_pct_stats": {
            "value": series_lp[-1] if series_lp else 0,
            "mean": mean_lp,
            "delta": delta_lp,
            "vol": vol_lp,
            "zscore": zscore_lp,
        },
    }


# -------------------------------------------------------------------------
# Trend Analysis Generation
# -------------------------------------------------------------------------
def build_trend_analysis(ps: Dict[str, Any], funding_rate_data: Optional[List[Dict[str, Any]]] = None) -> Dict[
    str, Any]:
    """
    Generate detailed trend analysis based on participant structure (ps) and funding rate.
    """
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

        # Map metric_key to stats key
        # ls_ratio -> ls_ratio_stats
        # long_pct -> long_pct_stats
        stats_key = f"{metric_key}_stats"

        for p in PERIODS:
            period_data = ps[type_name].get(p, {})
            # period_data structure: { 'current': {...}, 'ls_ratio_stats': {...}, 'long_pct_stats': {...} }

            stat_obj = period_data.get(stats_key, {})
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
    if funding_rate_data:
        # Re-calculate stats for funding rate to match structure
        # Funding rate is a single series, no periods.
        # We can map 'last' change as delta, and window zscore.
        fr_series = [float(x.get("fundingRate", 0.0)) for x in funding_rate_data[-30:]]
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

    return trends


# -------------------------------------------------------------------------
# Redis Raw Reader
# -------------------------------------------------------------------------
async def read_market_raw(exchange: str, symbol: str) -> Dict[str, Any]:
    cli = get_redis_client()
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


async def run_trend_analysis_pipeline(exchange: str, symbol: str) -> Dict[str, Any]:
    """
    Independent pipeline to fetch data and generate trend analysis.
    """
    # # Import here to avoid circular dependency
    # try:
    #     from api.application.apps.background.market_raw_analysis import read_market_raw
    # except ImportError:
    #     # Fallback for running as script from different context
    #     import sys
    #     import os
    #     _d = os.path.dirname(os.path.abspath(__file__))
    #     _root = os.path.abspath(os.path.join(_d, "..", "..", "..", ".."))
    #     if _root not in sys.path:
    #         sys.path.insert(0, _root)
    #     from api.application.apps.background.market_raw_analysis import read_market_raw

    # 1. Fetch Raw Data
    raw_data = await read_market_raw(exchange, symbol)

    # 2. Process into Participant Structure (intermediate step needed for trends)
    ps = {}
    for dtype in TYPES:
        ps[dtype] = {}
        for p in PERIODS:
            items = raw_data.get(dtype, {}).get(p, [])
            ps[dtype][p] = analyze_period(dtype, items)

    # 3. Generate Trends
    funding_data = raw_data.get("fundingRate", [])
    trends = build_trend_analysis(ps, funding_data)

    return {
        "symbol": symbol,
        "timestamp": int(time.time() * 1000),
        "trend_analysis": trends
    }


if __name__ == "__main__":
    import asyncio
    import json
    import os
    import sys

    # Path setup for direct execution
    _d = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.abspath(os.path.join(_d, "..", "..", "..", ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    res = asyncio.run(run_trend_analysis_pipeline("binance", "BTCUSDT"))
    print(json.dumps(res, ensure_ascii=False, indent=2))
