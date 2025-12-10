import json
from typing import Any, Dict, List, Optional
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
                interval = parts[3]
                dtype = parts[4]
            elif len(parts) == 4:
                interval = None
                dtype = parts[3]
            else:
                continue
            val = await cli.get(key)
            if not val:
                continue
            try:
                data = json.loads(val)
            except Exception:
                continue
            if interval is None and dtype in EXTRA_SIMPLE:
                target = EXTRA_SIMPLE[dtype]
                if target == "ticker24hr":
                    res[target] = data if isinstance(data, dict) else {}
                elif target == "fundingRate":
                    res[target] = data if isinstance(data, list) else [data]
                    
                continue
            if dtype not in TYPES:
                continue
            mapped_interval = "5m" if interval == "1m" else interval
            if mapped_interval not in PERIODS:
                continue
            res[dtype][mapped_interval] = data if isinstance(data, list) else [data]
        if cursor == 0:
            break
    return res


if __name__ == "__main__":
    import asyncio
    res = asyncio.run(read_market_raw(exchange="binance", symbol="BTCUSDT"))
    print(res)