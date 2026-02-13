import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

if __package__:
    from agent_server.utils.redis_client import get_verified_redis_client
    from ..io.background_kline import read_multi_period
    from ..io.raw_reader import PERIODS, read_market_raw
    from .build_context import build_fused_horizons, build_horizon_context
else:
    # 兼容“直接 python 运行脚本”的场景：向上查找包含 agent_server/agent_context 的仓库根目录并加入 sys.path
    _root = None
    for p in Path(__file__).resolve().parents:
        if (p / "agent_server" / "agent_context").is_dir():
            _root = str(p)
            break
    if _root and _root not in sys.path:
        sys.path.insert(0, _root)
    from agent_server.utils.redis_client import get_verified_redis_client
    from agent_server.agent_context.market_structure.io.background_kline import read_multi_period
    from agent_server.agent_context.market_structure.io.raw_reader import PERIODS, read_market_raw
    from agent_server.agent_context.market_structure.horizons.build_context import (
        build_fused_horizons,
        build_horizon_context,
    )


async def build_output(exchange: str, symbol: str) -> Dict[str, Any]:
    """从 Redis 读取 market_raw，并生成 horizon schema 的聚合输出。"""
    # 统一在同一个事件循环里创建并复用一个 Redis 客户端，避免同时使用 api/agent_server 两套初始化逻辑导致不一致
    client = await get_verified_redis_client()
    try:
        raw = await read_market_raw(exchange, symbol, client=client)
        kline_map = await read_multi_period(exchange, symbol, PERIODS, client=client)
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
    except Exception:
        raise



def main(exchange: str = "binance", symbol: str = "ETHUSDT") -> None:
    out = asyncio.run(build_output(exchange, symbol))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
