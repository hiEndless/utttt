"""
market_structure.holding_context_from_positions

从仓位列表 positions 中提取 open_time，计算持仓时长，并映射到持仓周期桶（short/mid/long）。
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from agent_server.agent_context.market_structure.horizon_schema import HORIZONS
from agent_server.agent_context.market_structure.holding_context import (
    format_duration_ms,
    match_horizon_by_duration,
)


def normalize_open_time_to_ms(value: Any, now_ms: int) -> int:
    # 将 open_time 归一化为毫秒时间戳：兼容 ms / s / 数字字符串 / ISO 字符串
    if value is None:
        return int(now_ms)

    if isinstance(value, (int, float)):
        ts = int(value)
    elif isinstance(value, str):
        s = value.strip()
        try:
            ts = int(float(s))
        except Exception:
            try:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return int(dt.timestamp() * 1000)
            except Exception:
                return int(now_ms)
    else:
        return int(now_ms)

    # 10 位左右通常为秒级时间戳；13 位左右通常为毫秒级
    if ts < 100_000_000_000:
        return int(ts * 1000)
    return int(ts)


def build_holding_context_from_positions(positions: Any, now_ts_ms: Optional[int] = None) -> Dict[str, Any]:
    # 如果 positions 里有多个仓位，取持仓时间最长的一笔（open_time 最早）为准
    now_ms = int(now_ts_ms if now_ts_ms is not None else time.time() * 1000)
    pos_list = positions if isinstance(positions, list) else []

    open_times_ms = [
        normalize_open_time_to_ms((p or {}).get("open_time"), now_ms)
        for p in pos_list
        if isinstance(p, dict)
    ]

    open_time_ms = int(min(open_times_ms)) if open_times_ms else int(now_ms)
    duration_ms = max(0, int(now_ms) - int(open_time_ms))

    horizon_key = match_horizon_by_duration(duration_ms)
    horizon_schema = HORIZONS.get(horizon_key, {})

    return {
        # "now_ts_ms": int(now_ms),
        # "open_time_ms": int(open_time_ms),
        # "duration_ms": int(duration_ms),
        "duration_human": format_duration_ms(duration_ms),
        "horizon": horizon_key,
        # "horizon_schema": horizon_schema,
    }


def main(exchange: Optional[str] = None, symbol: Optional[str] = None, positions_json: Optional[str] = None) -> None:
    # 优先使用 positions_json，其次用 get_position(exchange, symbol) 在线读取
    if positions_json:
        try:
            positions = json.loads(positions_json)
        except Exception:
            positions = []
    elif exchange and symbol:
        from agent_server.tools.get_position import get_position

        positions = get_position(exchange, symbol)
    else:
        positions = []

    out = build_holding_context_from_positions(positions)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="从仓位 positions 计算持仓时长与周期桶")
    parser.add_argument("--exchange", type=str, default=None)
    parser.add_argument("--symbol", type=str, default=None)
    parser.add_argument("--positions-json", type=str, default=None)
    args = parser.parse_args()

    main(exchange=args.exchange, symbol=args.symbol, positions_json=args.positions_json)

