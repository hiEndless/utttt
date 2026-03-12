"""orderbook.rolling: 基于短窗口（1s/5s/30s）的滚动结构结论与风险旗标。"""

from __future__ import annotations

from statistics import mean, pstdev
from typing import Any, Dict, List

from .metrics import mean_or_last, median


def window_frames(frames: List[Dict[str, Any]], *, now_ts: int, window_ms: int) -> List[Dict[str, Any]]:
    if window_ms <= 0:
        return []
    start = now_ts - window_ms
    return [f for f in frames if int(f.get("ts", 0)) >= start]


def imbalance_trend_30s(frames_30s: List[Dict[str, Any]]) -> str:
    if len(frames_30s) < 3:
        return "stable"
    first = float(frames_30s[0].get("imbalance_10", 0.5))
    last = float(frames_30s[-1].get("imbalance_10", 0.5))
    delta = last - first
    # imbalance_10 ∈ [0,1]，30s 内小幅波动在活跃时段很常见：这里表达“偏向在增加”，避免被误解为强趋势增强
    if delta >= 0.05:
        return "bid_bias_increasing"
    if delta <= -0.05:
        return "ask_bias_increasing"
    return "stable"


def wall_persistence(frames_30s: List[Dict[str, Any]], *, side: str) -> str:
    if len(frames_30s) < 3:
        return "flickering"
    key = "bid_wall_ratio" if side == "bid" else "ask_wall_ratio"
    price_key = "bid_wall_price" if side == "bid" else "ask_wall_price"
    present = 0
    total = 0
    wall_prices: List[float] = []
    for f in frames_30s:
        v = float(f.get(key, 0.0))
        total += 1
        if v >= 0.35:
            present += 1
            px = f.get(price_key)
            if px is not None:
                try:
                    pxf = float(px)
                    if pxf > 0:
                        wall_prices.append(pxf)
                except (TypeError, ValueError):
                    continue
    if total <= 0:
        return "flickering"
    ratio = present / total
    if ratio < 0.7:
        return "flickering"
    if len(wall_prices) < 3:
        return "persistent"

    # 防“假墙”：即使出现比例高，如果墙位价格在 30s 内漂移过大，也降级为 flickering
    spreads = [float(f.get("spread", 0.0)) for f in frames_30s if f.get("spread") is not None]
    spread_mean = mean_or_last(spreads)
    wall_med = median(wall_prices)
    if wall_med > 0:
        tol = max(spread_mean * 3.0, wall_med * 0.001)
        if (max(wall_prices) - min(wall_prices)) > tol:
            return "flickering"
    return "persistent"


def spread_state(frames_1s: List[Dict[str, Any]], frames_5s: List[Dict[str, Any]], frames_30s: List[Dict[str, Any]]) -> str:
    spreads_30 = [float(f.get("spread", 0.0)) for f in frames_30s if f.get("spread") is not None]
    spreads_5 = [float(f.get("spread", 0.0)) for f in frames_5s if f.get("spread") is not None]
    spreads_1 = [float(f.get("spread", 0.0)) for f in frames_1s if f.get("spread") is not None]
    if len(spreads_30) < 6 or len(spreads_5) < 2 or len(spreads_1) < 1:
        return "stable"

    m30 = mean(spreads_30)
    m5 = mean(spreads_5)
    m1 = mean(spreads_1)
    if m30 <= 0:
        return "stable"

    if m1 > m5 * 1.1 and m5 > m30 * 1.05:
        return "widening"
    if m1 < m5 * 0.9 and m5 < m30 * 0.95:
        return "tightening"
    return "stable"


def liquidity_stability(frames_5s: List[Dict[str, Any]], frames_30s: List[Dict[str, Any]]) -> str:
    if len(frames_30s) < 6 or len(frames_5s) < 2:
        return "unknown"

    depths_30 = [float(f.get("depth_notional_20", 0.0)) for f in frames_30s if f.get("depth_notional_20") is not None]
    spreads_30 = [float(f.get("spread", 0.0)) for f in frames_30s if f.get("spread") is not None]
    depths_5 = [float(f.get("depth_notional_20", 0.0)) for f in frames_5s if f.get("depth_notional_20") is not None]
    spreads_5 = [float(f.get("spread", 0.0)) for f in frames_5s if f.get("spread") is not None]
    if len(depths_30) < 6 or len(spreads_30) < 6 or len(depths_5) < 2 or len(spreads_5) < 2:
        return "unknown"

    d30_mean = mean(depths_30)
    d30_std = pstdev(depths_30) if len(depths_30) >= 2 else 0.0
    cv30 = (d30_std / d30_mean) if d30_mean > 0 else 0.0

    d5_mean = mean(depths_5)
    d5_std = pstdev(depths_5) if len(depths_5) >= 2 else 0.0
    cv5 = (d5_std / d5_mean) if d5_mean > 0 else 0.0

    s30_mean = mean(spreads_30)
    s30_std = pstdev(spreads_30) if len(spreads_30) >= 2 else 0.0
    scv30 = (s30_std / s30_mean) if s30_mean > 0 else 0.0

    s5_mean = mean(spreads_5)
    s5_std = pstdev(spreads_5) if len(spreads_5) >= 2 else 0.0
    scv5 = (s5_std / s5_mean) if s5_mean > 0 else 0.0

    if cv5 >= 0.4 or cv30 >= 0.35 or scv5 >= 0.7 or scv30 >= 0.5:
        return "fragile"
    return "stable"


def compute_orderbook_structure_short(frames: List[Dict[str, Any]], *, now_ts: int) -> Dict[str, Any]:
    frames_1s = window_frames(frames, now_ts=now_ts, window_ms=1_000)
    frames_5s = window_frames(frames, now_ts=now_ts, window_ms=5_000)
    frames_30s = window_frames(frames, now_ts=now_ts, window_ms=30_000)
    return {
        "imbalance_trend_30s": imbalance_trend_30s(frames_30s),
        "wall_persistence": {
            "ask_wall": wall_persistence(frames_30s, side="ask"),
            "bid_wall": wall_persistence(frames_30s, side="bid"),
        },
        "spread_state": spread_state(frames_1s, frames_5s, frames_30s),
        "liquidity_stability": liquidity_stability(frames_5s, frames_30s),
    }


def compute_orderbook_risk_flags(frames: List[Dict[str, Any]], *, now_ts: int) -> Dict[str, Any]:
    frames_1s = window_frames(frames, now_ts=now_ts, window_ms=1_000)
    spreads_1s = [float(f.get("spread", 0.0)) for f in frames_1s if f.get("spread") is not None]

    frames_30s = window_frames(frames, now_ts=now_ts, window_ms=30_000)
    spreads_30 = [float(f.get("spread", 0.0)) for f in frames_30s if f.get("spread") is not None]
    depths_30 = [float(f.get("depth_notional_20", 0.0)) for f in frames_30s if f.get("depth_notional_20") is not None]

    spread_mean = mean_or_last(spreads_30)
    spread_std = pstdev(spreads_30) if len(spreads_30) >= 6 else 0.0
    depth_med = median(depths_30)

    cur = frames[-1] if frames else {}
    cur_spread = float(cur.get("spread", 0.0))
    cur_depth = float(cur.get("depth_notional_20", 0.0))

    spread_anomaly = False
    local_peak = max(spreads_1s) if spreads_1s else cur_spread
    if spread_mean > 0 and local_peak > max(spread_mean * 2.0, spread_mean + 2.0 * spread_std):
        spread_anomaly = True

    liquidity_vacuum_event = False
    if depth_med > 0 and cur_depth < depth_med * 0.5 and spread_anomaly:
        liquidity_vacuum_event = True

    return {
        "liquidity_vacuum_event": bool(liquidity_vacuum_event),
        # 这是异常提示，不必然等价于风险事件
        "spread_anomaly": bool(spread_anomaly),
    }
