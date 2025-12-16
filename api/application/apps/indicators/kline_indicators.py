import json
import os
import sys
from typing import Any, Dict, List, Optional

_d = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_d, "..", "..", "..", ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

try:
    from ...common.redis_client import redis_client
except ImportError:
    from api.application.common.redis_client import redis_client


async def read_kline_indicators(
    exchange: str,
    symbol: str,
    interval: str,
    client: Optional[object] = None,
) -> Dict[str, Any]:
    cli = client or redis_client
    k_ind = f"indicators:{exchange}:{symbol}:{interval}"
    k_prev = f"indicators:prev:{exchange}:{symbol}:{interval}"
    k_kl = f"klines:{exchange}:{symbol}:{interval}"

    ind_raw = await cli.get(k_ind)
    prev_raw = await cli.get(k_prev)
    kl_raw = await cli.get(k_kl)

    ind = json.loads(ind_raw) if ind_raw else {}
    prev = json.loads(prev_raw) if prev_raw else {}
    kl = json.loads(kl_raw) if kl_raw else []

    return {
        "exchange": exchange,
        "symbol": symbol,
        "interval": interval,
        "indicators": ind,
        "prev_indicators": prev,
        "klines": kl,
    }

async def read_indicators(
    exchange: str,
    symbol: str,
    interval: str,
    client: Optional[object] = None,
) -> Dict[str, Any]:
    cli = client or redis_client
    k_ind = f"indicators:{exchange}:{symbol}:{interval}"
    ind_raw = await cli.get(k_ind)
    return json.loads(ind_raw) if ind_raw else {}


async def scan_symbols(
    exchange: str,
    interval: str,
    client: Optional[object] = None,
) -> List[str]:
    cli = client or redis_client
    cursor = 0
    pattern = f"indicators:{exchange}:*:{interval}"
    out: List[str] = []
    seen = set()
    while True:
        cursor, keys = await cli.scan(cursor=cursor, match=pattern, count=1000)
        for k in keys:
            parts = k.split(":")
            if len(parts) == 4:
                sym = parts[2]
                if sym not in seen:
                    seen.add(sym)
                    out.append(sym)
        if cursor == 0:
            break
    return out


async def read_multi_period(
    exchange: str,
    symbol: str,
    intervals: List[str],
    client: Optional[object] = None,
) -> Dict[str, Any]:
    cli = client or redis_client
    res: Dict[str, Any] = {}
    for itv in intervals:
        res[itv] = await read_indicators(exchange, symbol, itv, cli)
    return res


if __name__ == "__main__":
    import asyncio
    data = asyncio.run(read_indicators("binance", "BTCUSDT", "15m"))
    print(json.dumps(data, ensure_ascii=False))
