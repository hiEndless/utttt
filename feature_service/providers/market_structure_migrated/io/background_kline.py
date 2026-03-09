import json
from typing import Any, Dict, List, Optional

from feature_service.providers.market_structure_migrated.utils.redis_client import get_redis_client

# 说明：该模块读取 background kline（Redis key: background:{exchange}:{symbol}:{interval}）
# 目的：为 feature_service 迁移结构层提供统一背景数据读取能力
redis_client = get_redis_client()


DEFAULT_INTERVALS = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]


async def read_background(
    exchange: str,
    symbol: str,
    interval: str,
    client: Optional[object] = None,
) -> Dict[str, Any]:
    # 从 Redis 读取单周期背景数据
    cli = client or redis_client
    key = f"background:{exchange}:{symbol}:{interval}"
    raw = await cli.get(key)
    return json.loads(raw) if raw else {}


async def read_multi_period(
    exchange: str,
    symbol: str,
    intervals: List[str],
    client: Optional[object] = None,
) -> Dict[str, Any]:
    # 批量读取多周期背景数据
    cli = client or redis_client
    out: Dict[str, Any] = {}
    for itv in intervals:
        out[itv] = await read_background(exchange, symbol, itv, cli)
    return out


async def scan_symbols(exchange: str, client: Optional[object] = None) -> List[str]:
    # 扫描 background:{exchange}:*:* 中出现过的 symbol
    cli = client or redis_client
    cursor = 0
    pattern = f"background:{exchange}:*:*"
    res: List[str] = []
    seen = set()
    while True:
        cursor, keys = await cli.scan(cursor=cursor, match=pattern, count=1000)
        for k in keys:
            parts = str(k).split(":")
            if len(parts) == 4:
                sym = parts[2]
                if sym not in seen:
                    seen.add(sym)
                    res.append(sym)
        if cursor == 0:
            break
    return res


async def scan_intervals(exchange: str, symbol: str, client: Optional[object] = None) -> List[str]:
    # 扫描 background:{exchange}:{symbol}:* 中出现过的 interval
    cli = client or redis_client
    cursor = 0
    pattern = f"background:{exchange}:{symbol}:*"
    res: List[str] = []
    seen = set()
    while True:
        cursor, keys = await cli.scan(cursor=cursor, match=pattern, count=1000)
        for k in keys:
            parts = str(k).split(":")
            if len(parts) == 4:
                itv = parts[3]
                if itv not in seen:
                    seen.add(itv)
                    res.append(itv)
        if cursor == 0:
            break
    return res
