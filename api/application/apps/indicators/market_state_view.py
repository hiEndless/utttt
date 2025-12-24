import json
import os
import sys
from typing import Any, Dict, Optional

_d = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_d, "..", "..", "..", ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

try:
    from ...common.redis_client import redis_client
except ImportError:
    from api.application.common.redis_client import redis_client


def _drop_raw_trends(ms: Dict[str, Any]) -> Dict[str, Any]:
    market_state = ms.get("market_state") or {}
    for k, v in market_state.items():
        if isinstance(v, dict) and "_raw_trends" in v:
            v.pop("_raw_trends", None)
    return ms


async def read_full_market_state(
    exchange: str,
    symbol: str,
    client: Optional[object] = None,
) -> Dict[str, Any]:
    cli = client or redis_client
    key = f"background:{exchange}:{symbol}:market_state"
    raw = await cli.get(key)
    return json.loads(raw) if raw else {}



if __name__ == "__main__":
    import asyncio
    data = asyncio.run(read_full_market_state("binance", "BTCUSDT"))
    print(json.dumps(_drop_raw_trends(data), ensure_ascii=False))
