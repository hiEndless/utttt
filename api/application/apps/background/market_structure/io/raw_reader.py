from typing import Any, Dict, List, Optional
import json

from api.application.common.redis_client import redis_client


PERIODS = ["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]
TYPES = [
    "globalLongShortAccountRatio",
    "takerLongShortRatio",
    "topLongShortPositionRatio",
    "topLongShortAccountRatio",
]

INTERVAL_SERIES_TYPES = [
    "openInterestHist",
]

EXTRA_SIMPLE = {
    "24hr": "24hr",
    "fundingRate": "fundingRate",
    "openInterest": "openInterest",
}


def _init_result() -> Dict[str, Any]:
    base = {t: {p: [] for p in PERIODS} for t in TYPES}
    base["24hr"] = {}
    base["fundingRate"] = []
    base["openInterest"] = {}
    base["klines"] = {p: [] for p in PERIODS}
    base["openInterestHist"] = {p: [] for p in PERIODS}
    return base


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

            if interval is None and dtype in EXTRA_SIMPLE:
                if dtype == "24hr" and isinstance(data, dict):
                    res["24hr"] = data
                elif dtype == "fundingRate":
                    if isinstance(data, list):
                        res["fundingRate"] = data
                    else:
                        res["fundingRate"] = [data]
                elif dtype == "openInterest" and isinstance(data, dict):
                    res["openInterest"] = data
                continue

            mapped = "5m" if interval == "1m" else interval
            if mapped not in PERIODS:
                continue

            if dtype in TYPES:
                res[dtype][mapped] = data if isinstance(data, list) else [data]
                continue

            if dtype in INTERVAL_SERIES_TYPES:
                res[dtype][mapped] = data if isinstance(data, list) else [data]
                continue

        if cursor == 0:
            break

    for p in PERIODS:
        key = f"klines:{exchange}:{symbol}:{p}"
        raw = await cli.get(key)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        res["klines"][p] = data if isinstance(data, list) else [data]

    return res
