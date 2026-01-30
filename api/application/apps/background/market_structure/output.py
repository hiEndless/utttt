import asyncio
import json
import os
import sys
from typing import Any, Dict

if __package__:
    from .build_context import build_fused_horizons, build_horizon_context
    from .raw_reader import PERIODS, read_market_raw
    from ..background_kline import read_multi_period
else:
    _d = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.abspath(os.path.join(_d, "..", "..", "..", "..", ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from api.application.apps.background.market_structure.build_context import build_fused_horizons, build_horizon_context
    from api.application.apps.background.market_structure.raw_reader import PERIODS, read_market_raw
    from api.application.apps.background.background_kline import read_multi_period


async def build_output(exchange: str, symbol: str) -> Dict[str, Any]:
    """从 Redis 读取 market_raw，并生成 horizon schema 的聚合输出。"""
    raw = await read_market_raw(exchange, symbol)
    kline_map = await read_multi_period(exchange, symbol, PERIODS)
    kline_backgrounds = []
    for itv, payload in (kline_map or {}).items():
        if isinstance(payload, dict) and payload:
            merged = {"interval": itv}
            merged.update(payload)
            kline_backgrounds.append(merged)
    return {
        "base": build_horizon_context(raw, symbol),
        "fused": build_fused_horizons(raw, symbol, kline_backgrounds),
    }


def main(exchange: str = "binance", symbol: str = "ETHUSDT") -> None:
    """本地快速预览 horizon schema 输出结构。"""
    out = asyncio.run(build_output(exchange, symbol))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
