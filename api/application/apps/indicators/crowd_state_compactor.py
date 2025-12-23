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


async def read_market_structure(
    exchange: str,
    symbol: str,
    client: Optional[object] = None,
) -> Dict[str, Any]:
    cli = client or redis_client
    key = f"background:{exchange}:{symbol}:market_structure"
    raw = await cli.get(key)
    return json.loads(raw) if raw else {}


async def scan_symbols(
    exchange: str,
    client: Optional[object] = None,
) -> List[str]:
    cli = client or redis_client
    cursor = 0
    pattern = f"background:{exchange}:*:market_structure"
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


if __name__ == "__main__":
    import asyncio
    data = asyncio.run(read_market_structure("binance", "BTCUSDT"))
    print(json.dumps(data, ensure_ascii=False))
