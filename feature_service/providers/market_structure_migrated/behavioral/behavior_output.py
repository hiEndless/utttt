import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__:
    from feature_service.providers.market_structure_migrated.utils.redis_client import get_redis_client
    from feature_service.providers.market_structure_migrated.horizon_schema import HORIZONS
    from .behavior_aggregate import build_behavioral_structure_from_aggtrades, parse_window_to_ms
else:
    # 兼容“直接 python 运行脚本”的场景：向上查找包含 feature_service 的仓库根目录并加入 sys.path
    _root = None
    for p in Path(__file__).resolve().parents:
        if (p / "feature_service").is_dir():
            _root = str(p)
            break
    if _root and _root not in sys.path:
        sys.path.insert(0, _root)
    from feature_service.providers.market_structure_migrated.utils.redis_client import get_redis_client
    from feature_service.providers.market_structure_migrated.horizon_schema import HORIZONS
    from feature_service.providers.market_structure_migrated.behavioral.behavior_aggregate import (
        build_behavioral_structure_from_aggtrades,
        parse_window_to_ms,
    )

# 统一使用 feature_service 迁移层 Redis 连接，避免跨模块重复初始化导致的不一致
# 移除模块级全局 redis_client，改为在函数内动态获取，确保与当前事件循环绑定


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
    cli = client or get_redis_client()
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
    cli = client or get_redis_client()
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
    max_ms = _max_behavior_window_ms()
    now_ms = int(time.time() * 1000)
    client = get_redis_client()
    available_since_ms = await read_aggtrade_stream_available_since_ms(exchange, symbol, client)
    items = await read_recent_aggtrades(exchange, symbol, max_ms, now_ms=now_ms, client=client)
    return build_behavioral_structure_from_aggtrades(
        symbol,
        items,
        now_ms=now_ms,
        source="aggTrade",
        available_since_ms=available_since_ms,
    )


def main(exchange: str = "binance", symbol: str = "ETHUSDT") -> None:
    out = asyncio.run(build_behavior_output(exchange, symbol))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
