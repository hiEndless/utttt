# -------------------------------------------------------------------------
# Redis Raw Reader
# -------------------------------------------------------------------------
from typing import Any, Dict, List, Optional
import json

try:
    from ....common.redis_client import redis_client
except ImportError:
    from api.application.common.redis_client import redis_client

PERIODS = ["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]
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
    base["klines"] = {p: [] for p in PERIODS}
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
