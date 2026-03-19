"""
technical_context

从 Redis 的 klines:*（Binance K线数组）提取可量化的“周期性/空间”特征：
- 近期摆动高低点（swing_high/swing_low）
- 区间位置（range_position）
- 波动/ATR（atr、atr_pct）
- 距离关键位的空间（dist_to_high_pct / dist_to_low_pct）

用途：
1) 过滤“趋势上行但已到近期高点”的追多/追空
2) 为 TP/SL 提供更可解释的锚点（接近阻力/支撑）
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple

from agent_server.utils.redis_client import get_redis_client


def _to_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _parse_kline_row(row: Any) -> Optional[Tuple[int, float, float, float, float]]:
    """
    Binance kline row format (common):
    [
      open_time, open, high, low, close, volume, close_time, quote_volume, trades, ...
    ]
    """
    if not isinstance(row, (list, tuple)) or len(row) < 5:
        return None
    open_time = int(_to_float(row[0], 0))
    o = _to_float(row[1], 0.0)
    h = _to_float(row[2], 0.0)
    l = _to_float(row[3], 0.0)
    c = _to_float(row[4], 0.0)
    if open_time <= 0 or h <= 0 or l <= 0 or c <= 0:
        return None
    return open_time, o, h, l, c


def _compute_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
    """
    简化 ATR（Wilder 版可选，这里用 SMA(TR) 近似足够用于“空间/波动”门控）。
    """
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        return 0.0
    trs: List[float] = []
    for i in range(1, n):
        h = highs[i]
        l = lows[i]
        prev_c = closes[i - 1]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        if tr > 0:
            trs.append(tr)
    if len(trs) < period:
        return 0.0
    window = trs[-period:]
    return sum(window) / float(len(window))


def compute_technical_features_from_klines(
    klines: List[Any],
    ref_price: Optional[float] = None,
    window_bars: int = 96,
    atr_period: int = 14,
) -> Dict[str, Any]:
    rows: List[Tuple[int, float, float, float, float]] = []
    for r in klines or []:
        parsed = _parse_kline_row(r)
        if parsed:
            rows.append(parsed)

    if not rows:
        return {
            "status": "no_data",
            "bars_used": 0,
        }

    rows = rows[-min(len(rows), int(window_bars)) :]
    highs = [x[2] for x in rows]
    lows = [x[3] for x in rows]
    closes = [x[4] for x in rows]
    last_close = closes[-1]

    px = float(ref_price) if (ref_price is not None and ref_price > 0) else float(last_close)

    swing_high = max(highs) if highs else 0.0
    swing_low = min(lows) if lows else 0.0
    atr = _compute_atr(highs, lows, closes, period=int(atr_period))
    atr_pct = (atr / px) if (atr > 0 and px > 0) else 0.0

    denom = swing_high - swing_low
    if denom > 0 and px > 0:
        range_position = (px - swing_low) / denom
        range_position = max(0.0, min(1.0, float(range_position)))
    else:
        range_position = 0.5

    dist_to_high_pct = ((swing_high - px) / px) if (px > 0 and swing_high > 0) else 0.0
    dist_to_low_pct = ((px - swing_low) / px) if (px > 0 and swing_low > 0) else 0.0

    near_band = max(atr_pct * 0.8, 0.01)  # 贴近关键位的“周期末端/突破失败风险”带宽
    near_swing_high = bool(dist_to_high_pct >= 0 and dist_to_high_pct <= near_band)
    near_swing_low = bool(dist_to_low_pct >= 0 and dist_to_low_pct <= near_band)

    # 简单“突破确认”代理：超过 swing_high/low 一点点才算突破（避免等于/轻微刺破）
    breakout_eps = max(atr_pct * 0.25, 0.002)
    broke_above_swing_high = bool(px >= swing_high * (1.0 + breakout_eps)) if swing_high > 0 else False
    broke_below_swing_low = bool(px <= swing_low * (1.0 - breakout_eps)) if swing_low > 0 else False

    return {
        "status": "ok",
        "bars_used": len(rows),
        "ref_price": px,
        "last_close": float(last_close),
        "swing_high": float(swing_high),
        "swing_low": float(swing_low),
        "range_position": float(round(range_position, 4)),
        "atr": float(atr),
        "atr_pct": float(round(atr_pct, 6)),
        "dist_to_high_pct": float(round(dist_to_high_pct, 6)),
        "dist_to_low_pct": float(round(dist_to_low_pct, 6)),
        "near_swing_high": bool(near_swing_high),
        "near_swing_low": bool(near_swing_low),
        "broke_above_swing_high": bool(broke_above_swing_high),
        "broke_below_swing_low": bool(broke_below_swing_low),
    }


async def read_klines_from_redis(
    exchange: str,
    symbol: str,
    interval: str,
    client: Optional[object] = None,
) -> List[Any]:
    cli = client or get_redis_client()
    key = f"klines:{exchange}:{symbol}:{interval}"
    raw = await cli.get(key)
    if not raw:
        return []
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return []
    return data if isinstance(data, list) else []


async def build_technical_context(
    exchange: str,
    symbol: str,
    ref_price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    输出给 TradeDecision 的 technical_context。
    约定：
    - short_term 使用 15m（近 24h = 96 bars）
    - mid_term 使用 1h（近 7d = 168 bars）
    """
    cli = get_redis_client()
    k15_task = read_klines_from_redis(exchange, symbol, "15m", client=cli)
    k1h_task = read_klines_from_redis(exchange, symbol, "1h", client=cli)
    k15, k1h = await k15_task, await k1h_task

    short_term = compute_technical_features_from_klines(
        k15, ref_price=ref_price, window_bars=96, atr_period=14
    )
    short_term["interval"] = "15m"

    mid_term = compute_technical_features_from_klines(
        k1h, ref_price=ref_price, window_bars=168, atr_period=14
    )
    mid_term["interval"] = "1h"

    return {
        "symbol": symbol,
        "exchange": exchange,
        "ts": int(time.time() * 1000),
        "short_term": short_term,
        "mid_term": mid_term,
    }

