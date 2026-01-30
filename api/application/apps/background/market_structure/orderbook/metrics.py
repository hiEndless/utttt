"""orderbook.metrics: 从单帧 depth 快照中提取结构特征（不含时间滚动统计）。"""

from __future__ import annotations

from statistics import mean
from typing import Any, Dict, List, Tuple


def safe_float(x: Any) -> float | None:
    try:
        v = float(x)
        if v != v or v in (float("inf"), float("-inf")):
            return None
        return v
    except Exception:
        return None


def parse_levels(levels: Any, *, side: str, limit: int = 20) -> List[Tuple[float, float]]:
    if not isinstance(levels, list):
        return []
    out: List[Tuple[float, float]] = []
    for p in levels[: max(0, int(limit))]:
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            continue
        px = safe_float(p[0])
        qty = safe_float(p[1])
        if px is None or qty is None or qty <= 0:
            continue
        out.append((px, qty))

    if side == "bid":
        out.sort(key=lambda x: x[0], reverse=True)
    else:
        out.sort(key=lambda x: x[0])
    return out


def sum_notional(levels: List[Tuple[float, float]]) -> float:
    s = 0.0
    for px, qty in levels:
        s += px * qty
    return float(s)


def build_frame_metrics(depth: Dict[str, Any], *, ts_ms: int) -> Dict[str, Any] | None:
    bids = parse_levels(depth.get("bids"), side="bid", limit=20)
    asks = parse_levels(depth.get("asks"), side="ask", limit=20)
    if not bids or not asks:
        return None

    best_bid = bids[0][0]
    best_ask = asks[0][0]
    if best_ask <= 0 or best_bid <= 0:
        return None

    spread = float(best_ask - best_bid)
    bids10 = bids[:10]
    asks10 = asks[:10]
    bid_notional_10 = sum_notional(bids10)
    ask_notional_10 = sum_notional(asks10)
    denom = bid_notional_10 + ask_notional_10
    imbalance_10 = float(bid_notional_10 / denom) if denom > 0 else 0.5

    bid_top1_notional = float(bids[0][0] * bids[0][1])
    ask_top1_notional = float(asks[0][0] * asks[0][1])
    top1_wall_ratio = float(max(bid_top1_notional, ask_top1_notional) / denom) if denom > 0 else 0.0

    bid_wall_ratio = float(bid_top1_notional / bid_notional_10) if bid_notional_10 > 0 else 0.0
    ask_wall_ratio = float(ask_top1_notional / ask_notional_10) if ask_notional_10 > 0 else 0.0

    depth_notional_20 = float(sum_notional(bids) + sum_notional(asks))

    return {
        "ts": int(ts_ms),
        "spread": spread,
        "imbalance_10": imbalance_10,
        "top1_wall_ratio": top1_wall_ratio,
        "bid_wall_ratio": bid_wall_ratio,
        "ask_wall_ratio": ask_wall_ratio,
        # 记录“墙位”价格，用于识别假墙（大单但价格不断微调）
        "bid_wall_price": float(best_bid),
        "ask_wall_price": float(best_ask),
        "depth_notional_20": depth_notional_20,
    }


def liquidity_depth_score(depth_notional_20: float, history_depth: List[float]) -> str:
    if len(history_depth) >= 10:
        base = sorted(history_depth)[len(history_depth) // 2]
        if base <= 0:
            return "thin" if depth_notional_20 <= 0 else "normal"
        if depth_notional_20 < base * 0.7:
            return "thin"
        if depth_notional_20 > base * 1.3:
            return "thick"
        return "normal"

    if depth_notional_20 < 2e5:
        return "thin"
    if depth_notional_20 > 2e6:
        return "thick"
    return "normal"


def compute_orderbook_snapshot(frame: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "spread": round(float(frame.get("spread", 0.0)), 8),
        "bid_ask_imbalance_10": round(float(frame.get("imbalance_10", 0.5)), 4),
        "top1_wall_ratio": round(float(frame.get("top1_wall_ratio", 0.0)), 4),
        "liquidity_depth_score": str(frame.get("liquidity_depth_score", "unknown")),
    }


def median(xs: List[float]) -> float:
    if not xs:
        return 0.0
    ys = sorted(xs)
    return float(ys[len(ys) // 2])


def mean_or_last(xs: List[float]) -> float:
    if not xs:
        return 0.0
    if len(xs) == 1:
        return float(xs[0])
    return float(mean(xs))
