import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

if __package__:
    from .service import build_orderbook_structure
else:
    # 兼容“直接 python 运行脚本”的场景：向上查找包含 feature_service 的仓库根目录并加入 sys.path
    _root = None
    for p in Path(__file__).resolve().parents:
        if (p / "feature_service").is_dir():
            _root = str(p)
            break
    if _root and _root not in sys.path:
        sys.path.insert(0, _root)
    from feature_service.providers.market_structure_migrated.orderbook.service import build_orderbook_structure


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
