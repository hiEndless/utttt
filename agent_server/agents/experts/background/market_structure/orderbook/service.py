"""orderbook.service: 组合 depth 读取、单帧特征、滚动结论与缓存写入。"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from agent_server.utils.redis_client import get_redis_client

# 统一从 agent_server 层获取 Redis 连接，避免依赖 api 模块的 redis_client
redis_client = get_redis_client()

from .depth_reader import read_orderbook_depth_stream
from .metrics import build_frame_metrics, compute_orderbook_snapshot, liquidity_depth_score
from .rolling import compute_orderbook_risk_flags, compute_orderbook_structure_short


async def build_orderbook_structure(
    exchange: str,
    symbol: str,
    *,
    refresh: bool = True,
    depth_client: Optional[object] = None,
    cache_client: Optional[object] = None,
) -> Dict[str, Any]:
    _ = refresh
    _ = cache_client
    depth_cli = depth_client or redis_client

    history = await read_orderbook_depth_stream(exchange, symbol, client=depth_cli, count=300)
    if not history:
        return {}

    frames: list[dict] = []
    for item in history:
        ts_ms = int(item.get("ts", 0) or 0)
        depth = item.get("depth")
        if not isinstance(depth, dict) or ts_ms <= 0:
            continue
        fm = build_frame_metrics(depth, ts_ms=ts_ms)
        if fm is None:
            continue
        frames.append(fm)

    if not frames:
        return {}

    frames.sort(key=lambda x: int(x.get("ts", 0)))
    now_ts = int(frames[-1].get("ts") or int(time.time() * 1000))

    history_depth = [float(f.get("depth_notional_20", 0.0)) for f in frames[:-1] if f.get("depth_notional_20") is not None]
    frames[-1]["liquidity_depth_score"] = liquidity_depth_score(float(frames[-1]["depth_notional_20"]), history_depth)

    snapshot = compute_orderbook_snapshot(frames[-1])
    structure_short = compute_orderbook_structure_short(frames, now_ts=now_ts)
    risk_flags = compute_orderbook_risk_flags(frames, now_ts=now_ts)

    return {
        "ts": now_ts,
        "orderbook_snapshot": snapshot,
        "orderbook_structure_short": structure_short,
        "orderbook_risk_flags": risk_flags,
    }
