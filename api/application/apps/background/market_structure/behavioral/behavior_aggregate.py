from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from api.application.apps.background.market_structure.horizon_schema import HORIZONS


@dataclass(frozen=True)
class AggTrade:
    """聚合成交的最小字段集合（用于行为窗口聚合）。"""

    ts: int
    price: float
    qty: float
    is_buyer_maker: bool

    @property
    def quote_qty(self) -> float:
        return float(self.price) * float(self.qty)

    @property
    def is_buy_initiated(self) -> bool:
        """Binance 口径：m=True 代表买方是 maker => 卖方主动（sell initiated）。"""
        return not bool(self.is_buyer_maker)


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def parse_window_to_ms(window: str) -> int:
    """将行为窗口字符串解析为毫秒。

    支持：5s / 15s / 1m / 15m / 1h / 24h / 1d 等。
    """
    raw = (window or "").strip().lower()
    if not raw:
        return 0

    unit = raw[-1]
    num_str = raw[:-1]
    try:
        n = float(num_str)
    except Exception:
        return 0

    if unit == "s":
        return int(n * 1000)
    if unit == "m":
        return int(n * 60_000)
    if unit == "h":
        return int(n * 3_600_000)
    if unit == "d":
        return int(n * 86_400_000)
    return 0


MIN_EFFECTIVE_WINDOW_MS: Dict[str, int] = {
    "short_term": parse_window_to_ms("1m"),
    "mid_term": parse_window_to_ms("2h"),
    "long_term": parse_window_to_ms("12h"),
}


def _ms_to_iso(ms: Optional[int]) -> Optional[str]:
    if not ms:
        return None
    try:
        dt = datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def _liquidity_taking(total_quote_volume: float, window_ms: int) -> str:
    """根据单位时间成交额粗略划分流动性拿取强度。"""
    if window_ms <= 0:
        return "unknown"
    per_min = total_quote_volume / max(1.0, window_ms / 60_000.0)
    if per_min < 50_000:
        return "very_low"
    if per_min < 250_000:
        return "low"
    if per_min < 1_000_000:
        return "medium"
    return "high"


def _flow_label(buy_ratio: float, aggression_ratio: float, trade_count: int) -> str:
    """将窗口内指标压缩为可投票的流向标签（偏事实型，避免过早解释）。"""
    if trade_count <= 0:
        return "no_activity"
    if trade_count < 30:
        return "unclear"
    if aggression_ratio < 0.2:
        return "balanced"
    if buy_ratio >= 0.58:
        return "active_buy"
    if buy_ratio <= 0.42:
        return "active_sell"
    return "balanced"


def _market_mode(window_ms: int, trade_count: int, aggression_ratio: float, liquidity_taking: str) -> str:
    """将行为特征压缩为可读的市场模式标签。"""
    if trade_count <= 0:
        return "inactive"
    is_short = window_ms <= 60_000
    if is_short and aggression_ratio >= 0.5 and liquidity_taking in ("medium", "high"):
        return "emotion_driven"
    if aggression_ratio >= 0.35 and liquidity_taking in ("medium", "high"):
        return "trend_participation"
    if liquidity_taking in ("very_low", "low") and aggression_ratio < 0.2:
        return "passive_absorption"
    return "range_flow"


def _risk_flags(window_ms: int, trade_count: int, aggression_ratio: float, liquidity_taking: str) -> List[str]:
    """输出非方向性的风险标记（给风控/仓位管理更细粒度的“限制条件”）。"""
    flags: List[str] = []
    if trade_count > 0 and trade_count < 5:
        flags.append("thin_liquidity")
    if window_ms <= 60_000 and aggression_ratio >= 0.7:
        flags.append("overreaction_possible")
    if liquidity_taking == "high" and aggression_ratio >= 0.6:
        flags.append("liquidity_sweep_risk")
    if aggression_ratio >= 0.5 and liquidity_taking in ("very_low", "low"):
        flags.append("liquidity_not_following_aggression")
    return flags


def _state_tags(
    window_ms: int,
    trade_count: int,
    buy_ratio: float,
    aggression_ratio: float,
    liquidity_taking: str,
) -> List[str]:
    if trade_count <= 0:
        return ["no_activity"]

    tags: List[str] = []
    is_micro = window_ms < 30_000
    if buy_ratio >= 0.6:
        if is_micro and liquidity_taking in ("very_low", "low"):
            tags.append("probing_buy")
        else:
            tags.append("active_buying")
    elif buy_ratio <= 0.4:
        if is_micro and liquidity_taking in ("very_low", "low"):
            tags.append("probing_sell")
        else:
            tags.append("active_selling")
    else:
        tags.append("balanced_flow")

    if aggression_ratio >= 0.6:
        tags.append("strong_imbalance")
    elif aggression_ratio >= 0.3:
        tags.append("moderate_imbalance")
    else:
        tags.append("no_clear_leader")

    if window_ms < 30_000 and aggression_ratio >= 0.5:
        tags.append("micro_aggression")
    elif window_ms <= 60_000 and aggression_ratio >= 0.5:
        tags.append("short_term_aggression")
        if liquidity_taking in ("medium", "high"):
            tags.append("emotion_driven")

    tags.append(f"liquidity_{liquidity_taking}")
    return tags


def _normalize_trade(obj: Mapping[str, Any]) -> Optional[AggTrade]:
    """将任意字典/Redis 字段映射为 AggTrade；缺字段则丢弃。"""
    try:
        ts = int(float(obj.get("ts")))
        price = float(obj.get("price"))
        qty = float(obj.get("qty"))
        is_buyer_maker_raw = obj.get("is_buyer_maker")
        if isinstance(is_buyer_maker_raw, str):
            is_buyer_maker = is_buyer_maker_raw.strip().lower() in ("1", "true", "t", "yes", "y")
        else:
            is_buyer_maker = bool(is_buyer_maker_raw)
        return AggTrade(ts=ts, price=price, qty=qty, is_buyer_maker=is_buyer_maker)
    except Exception:
        return None


def normalize_trades(items: Iterable[Mapping[str, Any]]) -> List[AggTrade]:
    """批量归一化并按 ts 升序排序。"""
    out: List[AggTrade] = []
    for it in items:
        t = _normalize_trade(it)
        if t is not None:
            out.append(t)
    out.sort(key=lambda x: x.ts)
    return out


def compute_window_metrics(trades_sorted: List[AggTrade], now_ms: int, window_ms: int) -> Dict[str, Any]:
    """计算单个行为窗口的成交行为指标。"""
    if window_ms <= 0:
        return {
            "status": "invalid_window",
            "window_ms": int(window_ms),
            "trade_count": 0,
            "buy_ratio": 0.0,
            "aggression_ratio": 0.0,
            "avg_trade_size": 0.0,
            "delta_volume": 0.0,
            "liquidity_taking": "unknown",
            "state_tags": ["invalid_window"],
            "is_full_window": False,
            "coverage_ratio": 0.0,
            "coverage_ms": 0,
            "delta_volume_in_summary": False,
        }

    ts_list = [t.ts for t in trades_sorted]
    start_ts = int(now_ms) - int(window_ms)
    idx = bisect_left(ts_list, start_ts)
    window_trades = trades_sorted[idx:]

    trade_count = len(window_trades)
    if trade_count <= 0:
        return {
            "status": "no_activity",
            "window_ms": int(window_ms),
            "trade_count": 0,
            "buy_ratio": 0.0,
            "aggression_ratio": 0.0,
            "avg_trade_size": 0.0,
            "delta_volume": 0.0,
            "liquidity_taking": "very_low",
            "state_tags": ["no_activity"],
            "is_full_window": True,
            "coverage_ratio": 1.0,
            "coverage_ms": int(window_ms),
            "delta_volume_in_summary": window_ms >= 30_000,
        }

    buy_cnt = sum(1 for t in window_trades if t.is_buy_initiated)
    buy_ratio = buy_cnt / trade_count
    aggression_ratio = abs(buy_ratio - 0.5) * 2.0

    qtys = [t.qty for t in window_trades]
    avg_trade_size = _mean(qtys)

    delta_volume = 0.0
    total_quote_volume = 0.0
    for t in window_trades:
        qv = t.quote_qty
        total_quote_volume += qv
        delta_volume += qv if t.is_buy_initiated else -qv

    liq = _liquidity_taking(total_quote_volume, window_ms)
    tags = _state_tags(window_ms, trade_count, buy_ratio, aggression_ratio, liq)

    delta_in_summary = window_ms >= 30_000
    return {
        "status": "ok",
        "window_ms": int(window_ms),
        "trade_count": int(trade_count),
        "buy_ratio": round(float(buy_ratio), 2),
        "aggression_ratio": round(float(aggression_ratio), 2),
        "avg_trade_size": round(float(avg_trade_size), 6),
        "delta_volume": round(float(delta_volume), 6),
        "liquidity_taking": liq,
        "state_tags": tags,
        "is_full_window": True,
        "coverage_ratio": 1.0,
        "coverage_ms": int(window_ms),
        "delta_volume_in_summary": bool(delta_in_summary),
    }


def _pick_primary_window(behavior_windows: List[str]) -> Tuple[str, int]:
    best_w = ""
    best_ms = -1
    for w in behavior_windows:
        ms = parse_window_to_ms(w)
        if ms > best_ms:
            best_ms = ms
            best_w = w
    return best_w, max(0, best_ms)


def _maturity_status(horizon: str, coverage_ms: int) -> str:
    required = int(MIN_EFFECTIVE_WINDOW_MS.get(horizon, 0))
    if required <= 0:
        return "unknown"
    if horizon == "long_term":
        return "mature" if coverage_ms >= required else "unavailable"
    if coverage_ms <= 0:
        return "unavailable"
    return "mature" if coverage_ms >= required else "immature"


def _summary_from_votes(windows: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    votes: List[str] = []
    liq_votes: List[str] = []
    risk_flags: set[str] = set()
    aggressions: List[float] = []
    micro_strong_flows: List[str] = []
    for cell in (windows or {}).values():
        if not isinstance(cell, dict):
            continue
        if not bool(cell.get("is_full_window")):
            continue
        window_ms = int(cell.get("window_ms") or 0)
        if window_ms < 30_000:
            continue
        trade_count = int(cell.get("trade_count") or 0)
        buy_ratio = float(cell.get("buy_ratio") or 0.0)
        aggression_ratio = float(cell.get("aggression_ratio") or 0.0)
        flow = _flow_label(buy_ratio, aggression_ratio, trade_count)
        if flow in ("no_activity", "unclear"):
            continue
        votes.append(flow)
        liq_votes.append(str(cell.get("liquidity_taking") or "unknown"))
        aggressions.append(float(aggression_ratio))
        for f in list(cell.get("risk_flags") or []):
            risk_flags.add(str(f))
        if window_ms < 30_000 and flow in ("active_buy", "active_sell") and aggression_ratio >= 0.6:
            micro_strong_flows.append(flow)

    if not votes:
        return None

    total = len(votes)
    counts: Dict[str, int] = {}
    for v in votes:
        counts[v] = counts.get(v, 0) + 1
    dominant, dominant_cnt = sorted(counts.items(), key=lambda x: x[1], reverse=True)[0]
    dominant_ratio = dominant_cnt / max(1, total)
    dominant_flow = dominant if dominant_ratio >= 0.6 else "mixed"

    if total >= 3 and dominant_ratio >= 0.75:
        flow_confidence = "high"
    elif dominant_ratio >= 0.6:
        flow_confidence = "medium"
    else:
        flow_confidence = "low"

    avg_aggr = sum(aggressions) / len(aggressions) if aggressions else 0.0
    if avg_aggr < 0.25:
        range_stability = "high"
    elif avg_aggr < 0.4:
        range_stability = "medium"
    else:
        range_stability = "low"

    liq_level = "unknown"
    if any(x in ("high", "medium") for x in liq_votes):
        liq_level = "active"
    if dominant_flow == "mixed" and liq_level == "active":
        market_mode = "liquidity_active_range"
        risk_flags.add("unclear_flow")
    else:
        market_mode = "range_flow" if dominant_flow in ("mixed", "balanced") else "trend_driven"

    if micro_strong_flows and dominant_flow in ("balanced", "mixed"):
        risk_flags.add("no_follow_through")

    return {
        "dominant_flow": dominant_flow,
        "flow_confidence": flow_confidence,
        "market_mode": market_mode,
        "range_stability": range_stability,
        "risk_flags": sorted(list(risk_flags)),
    }


def build_behavioral_structure_from_aggtrades(
    symbol: str,
    aggtrades: Iterable[Mapping[str, Any]],
    now_ms: Optional[int] = None,
    source: str = "aggTrade",
    available_since_ms: Optional[int] = None,
) -> Dict[str, Any]:
    import time

    ts_now = int(now_ms if now_ms is not None else time.time() * 1000)
    trades = normalize_trades(aggtrades)
    first_ts = int(available_since_ms) if available_since_ms is not None else (trades[0].ts if trades else 0)
    coverage_ms = max(0, ts_now - int(first_ts)) if first_ts else 0

    data_maturity: Dict[str, str] = {}
    behavioral: Dict[str, Any] = {}
    for horizon, cfg in (HORIZONS or {}).items():
        behavior_windows = list(cfg.get("behavior_windows") or [])
        holding_window = cfg.get("holding_window")
        status = _maturity_status(horizon, coverage_ms)
        data_maturity[horizon] = status

        if horizon in ("mid_term", "long_term") and status != "mature":
            behavioral[horizon] = {
                "holding_window": holding_window,
                "status": "insufficient_data" if horizon == "mid_term" else "unavailable",
                "available_since": _ms_to_iso(first_ts),
                "required_min_window": "≥2h" if horizon == "mid_term" else "≥12h",
                "aggregation_windows": {},
                "summary": None,
            }
            continue

        aggregation_windows: Dict[str, Any] = {}
        for w in behavior_windows:
            w_ms = parse_window_to_ms(w)
            cell = compute_window_metrics(trades, ts_now, w_ms)
            if first_ts:
                cov_total = max(0, ts_now - first_ts)
                is_full = cov_total >= w_ms
                cov_ms = min(int(w_ms), int(cov_total))
                ratio = round(cov_ms / w_ms, 4) if w_ms > 0 else 0.0
                cell["is_full_window"] = bool(is_full)
                cell["coverage_ms"] = int(cov_ms)
                cell["coverage_ratio"] = float(ratio)
            else:
                cell["is_full_window"] = False
                cell["coverage_ms"] = 0
                cell["coverage_ratio"] = 0.0

            trade_count = int(cell.get("trade_count") or 0)
            aggression_ratio = float(cell.get("aggression_ratio") or 0.0)
            liq = str(cell.get("liquidity_taking") or "unknown")
            rr = _risk_flags(w_ms, trade_count, aggression_ratio, liq)
            if rr:
                cell["risk_flags"] = rr
            aggregation_windows[w] = cell

        summary: Optional[Dict[str, Any]] = None
        if horizon == "short_term":
            if coverage_ms >= int(MIN_EFFECTIVE_WINDOW_MS.get("short_term", 0)):
                summary = _summary_from_votes(aggregation_windows)
        else:
            summary = _summary_from_votes(aggregation_windows)

        behavioral[horizon] = {
            "holding_window": holding_window,
            "status": status,
            "available_since": _ms_to_iso(first_ts),
            "required_min_window": "≥1m"
            if horizon == "short_term"
            else ("≥2h" if horizon == "mid_term" else "≥12h"),
            "aggregation_windows": aggregation_windows,
            "summary": summary,
        }

    return {
        "symbol": symbol,
        "ts": ts_now,
        "source": source,
        "data_maturity": data_maturity,
        "behavioral_structure": behavioral,
    }
