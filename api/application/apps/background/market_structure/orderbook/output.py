import asyncio
import json
import os
import sys
import time
from typing import Any, Dict

if __package__:
    from .service import build_orderbook_structure
else:
    _d = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.abspath(os.path.join(_d, "..", "..", "..", "..", "..", ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from api.application.apps.background.market_structure.orderbook.service import build_orderbook_structure


async def build_output(exchange: str, symbol: str) -> Dict[str, Any]:
    data = await build_orderbook_structure(exchange, symbol, refresh=True)
    return {
        "symbol": symbol,
        "generated_at": int(time.time() * 1000),
        **(data or {}),
    }


def main(exchange: str = "binance", symbol: str = "ETHUSDT") -> None:
    out = asyncio.run(build_output(exchange, symbol))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

