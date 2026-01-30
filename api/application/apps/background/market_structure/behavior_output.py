import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

if __package__:
    from .behavior_aggregate import (
        build_behavioral_structure_from_aggtrades,
        parse_window_to_ms,
    )
    from .horizon_schema import HORIZONS
    from ....common.redis_client import redis_client
else:
    _d = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.abspath(os.path.join(_d, "..", "..", "..", "..", ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from api.application.apps.background.market_structure.behavior_aggregate import (
        build_behavioral_structure_from_aggtrades,
        parse_window_to_ms,
    )
    from api.application.apps.background.market_structure.horizon_schema import HORIZONS
    from api.application.common.redis_client import redis_client


def _max_behavior_window_ms() -> int:
    ms = 0
    for cfg in (HORIZONS or {}).values():
        for w in list(cfg.get("behavior_windows") or []):
            ms = max(ms, parse_window_to_ms(w))
    return ms


async def read_recent_aggtrades(
    exchange: str,
    symbol: str,
    max_window_ms: int,
    now_ms: Optional[int] = None,
    limit: int = 50000,
    client: Optional[object] = None,
) -> List[Dict[str, Any]]:
    """从 Redis Stream 读取近 max_window_ms 的 aggTrade 行为字段。"""
    cli = client or redis_client
    key = f"aggtrades:{exchange}:{symbol}"

    try:
        rows = await cli.xrevrange(key, max="+", min="-", count=int(limit))
    except Exception:
        rows = []

    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    since_ms = now_ms - int(max_window_ms)

    out: List[Dict[str, Any]] = []
    for _, fields in reversed(rows or []):
        if not isinstance(fields, dict):
            continue
        try:
            ts = int(float(fields.get("ts")))
        except Exception:
            continue
        if ts < since_ms:
            continue
        out.append(fields)
    return out


async def read_aggtrade_stream_available_since_ms(
    exchange: str,
    symbol: str,
    client: Optional[object] = None,
) -> Optional[int]:
    """读取 aggTrade Stream 的最早可用时间戳（用于数据成熟度判定）。"""
    cli = client or redis_client
    key = f"aggtrades:{exchange}:{symbol}"
    try:
        info = await cli.xinfo_stream(key)
    except Exception:
        return None
    if not isinstance(info, dict):
        return None
    first_entry = info.get("first-entry") or info.get("first_entry")
    if not first_entry or not isinstance(first_entry, (list, tuple)) or len(first_entry) < 2:
        return None
    fields = first_entry[1]
    if not isinstance(fields, dict):
        return None
    try:
        return int(float(fields.get("ts")))
    except Exception:
        return None


async def build_behavior_output(exchange: str, symbol: str) -> Dict[str, Any]:
    """从 Redis 读取 aggTrade stream，并生成按 behavior_windows 聚合的行为结构。"""
    max_ms = _max_behavior_window_ms()
    now_ms = int(time.time() * 1000)
    available_since_ms = await read_aggtrade_stream_available_since_ms(exchange, symbol, redis_client)
    items = await read_recent_aggtrades(exchange, symbol, max_ms, now_ms=now_ms, client=redis_client)
    return build_behavioral_structure_from_aggtrades(
        symbol,
        items,
        now_ms=now_ms,
        source="aggTrade",
        available_since_ms=available_since_ms,
    )


def main(exchange: str = "binance", symbol: str = "ETHUSDT") -> None:
    """本地快速预览 aggTrade 行为结构输出。"""
    out = asyncio.run(build_behavior_output(exchange, symbol))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
