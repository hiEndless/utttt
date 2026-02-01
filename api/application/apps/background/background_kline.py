import json
import os
import sys
from typing import Any, Dict, List, Optional

_d = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_d, "..", "..", "..", ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

try:
    from ...common.redis_client import get_async_redis_client
except ImportError:
    from api.application.common.redis_client import get_async_redis_client

DEFAULT_INTERVALS = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]


async def read_background_kline(
    exchange: str,
    symbol: str,
    interval: str,
    client: Optional[object] = None,
) -> Dict[str, Any]:
    cli = client or get_async_redis_client()
    k_bg = f"background:{exchange}:{symbol}:{interval}"
    raw = await cli.get(k_bg)
    data = json.loads(raw) if raw else {}
    return data


async def read_background(
    exchange: str,
    symbol: str,
    interval: str,
    client: Optional[object] = None,
) -> Dict[str, Any]:
    cli = client or get_async_redis_client()
    k_bg = f"background:{exchange}:{symbol}:{interval}"
    raw = await cli.get(k_bg)
    return json.loads(raw) if raw else {}


async def read_multi_period(
    exchange: str,
    symbol: str,
    intervals: List[str],
    client: Optional[object] = None,
) -> Dict[str, Any]:
    cli = client or get_async_redis_client()
    out: Dict[str, Any] = {}
    for itv in intervals:
        out[itv] = await read_background(exchange, symbol, itv, cli)
    return out


async def scan_symbols(
    exchange: str,
    client: Optional[object] = None,
) -> List[str]:
    cli = client or get_async_redis_client()
    cursor = 0
    pattern = f"background:{exchange}:*:*"
    res: List[str] = []
    seen = set()
    while True:
        cursor, keys = await cli.scan(cursor=cursor, match=pattern, count=1000)
        for k in keys:
            parts = k.split(":")
            if len(parts) == 4:
                sym = parts[2]
                if sym not in seen:
                    seen.add(sym)
                    res.append(sym)
        if cursor == 0:
            break
    return res


async def scan_intervals(
    exchange: str,
    symbol: str,
    client: Optional[object] = None,
) -> List[str]:
    cli = client or get_async_redis_client()
    cursor = 0
    pattern = f"background:{exchange}:{symbol}:*"
    res: List[str] = []
    seen = set()
    while True:
        cursor, keys = await cli.scan(cursor=cursor, match=pattern, count=1000)
        for k in keys:
            parts = k.split(":")
            if len(parts) == 4:
                itv = parts[3]
                if itv not in seen:
                    seen.add(itv)
                    res.append(itv)
        if cursor == 0:
            break
    return res


if __name__ == "__main__":
    import asyncio

    async def _main() -> None:
        data_single = await read_background_kline("binance", "RIVERUSDT", "15m")
        print(json.dumps(data_single, ensure_ascii=False))
        data_multi = await read_multi_period("binance", "RIVERUSDT", DEFAULT_INTERVALS)
        print(json.dumps(data_multi, ensure_ascii=False))

    asyncio.run(_main())
