import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

if __package__:
    from agent_server.utils.redis_client import get_redis_client
    from agent_server.agent_context.market_structure.io.raw_reader import PERIODS, read_market_raw
    from .analysis import analyze_open_interest_hist
else:
    # 兼容“直接 python 运行脚本”的场景：向上查找包含 agent_server/agent_context 的仓库根目录并加入 sys.path
    _root = None
    for p in Path(__file__).resolve().parents:
        if (p / "agent_server" / "agent_context").is_dir():
            _root = str(p)
            break
    if _root and _root not in sys.path:
        sys.path.insert(0, _root)
    from agent_server.utils.redis_client import get_redis_client
    from agent_server.agent_context.market_structure.io.raw_reader import PERIODS, read_market_raw
    from agent_server.agent_context.market_structure.open_interest.analysis import analyze_open_interest_hist

# 统一从 agent_server 层获取 Redis 连接，避免跨模块重复初始化导致的不一致
redis_client = get_redis_client()


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _coerce_open_interest_structure(open_interest_structure: Any) -> Dict[str, Any]:
    if not isinstance(open_interest_structure, dict):
        return {}
    out: Dict[str, Any] = {}
    for itv, cell in (open_interest_structure or {}).items():
        if not isinstance(cell, dict):
            continue
        state = cell.get("state") if isinstance(cell.get("state"), dict) else {}
        delta = cell.get("delta") if isinstance(cell.get("delta"), dict) else {}
        meta = cell.get("meta") if isinstance(cell.get("meta"), dict) else {}
        out[str(itv)] = dict(cell)
        out[str(itv)]["state"] = {
            **state,
            "open_interest": _safe_float(state.get("open_interest"), default=0.0),
            "open_interest_value": _safe_float(state.get("open_interest_value"), default=0.0),
            "oi_to_quote_volume_ratio": _safe_float(state.get("oi_to_quote_volume_ratio"), default=0.0),
        }
        out[str(itv)]["delta"] = {
            **delta,
            "delta_oi": _safe_float(delta.get("delta_oi"), default=0.0),
            "delta_oi_pct": _safe_float(delta.get("delta_oi_pct"), default=0.0),
        }
        if isinstance(meta, dict):
            out[str(itv)]["meta"] = dict(meta)
    return out


def _kline_close(k: Any) -> Optional[float]:
    if isinstance(k, (list, tuple)) and len(k) >= 5:
        c = _safe_float(k[4], default=0.0)
        return None if c == 0.0 else c
    if isinstance(k, dict):
        for key in ("close", "c", "closePrice", "close_price"):
            if key in k:
                c = _safe_float(k.get(key), default=0.0)
                return None if c == 0.0 else c
    return None


def _trend_pct(pct: float, eps_pct: float = 0.01) -> str:
    if abs(pct) < eps_pct:
        return "flat"
    return "up" if pct > 0 else "down"


def analyze_price_trends_from_klines(klines_by_interval: Mapping[str, Any], intervals: list[str]) -> Dict[str, Any]:
    if not klines_by_interval:
        return {"price_change_pct": {}, "trends": {}, "latest_close": {}}

    changes: Dict[str, float] = {}
    trends: Dict[str, str] = {}
    latest_close: Dict[str, float] = {}

    for interval in intervals:
        klines = klines_by_interval.get(interval) or []
        if not isinstance(klines, list) or len(klines) < 2:
            continue

        prev = _kline_close(klines[-2])
        last = _kline_close(klines[-1])
        if prev is None or last is None or prev == 0:
            continue

        pct = (last - prev) / prev * 100.0
        changes[interval] = round(pct, 4)
        trends[interval] = _trend_pct(pct)
        latest_close[interval] = last

    return {"price_change_pct": changes, "trends": trends, "latest_close": latest_close}


def _taker_bias_from_ratio(buy_sell_ratio: float) -> str:
    if buy_sell_ratio > 1.05:
        return "long"
    if buy_sell_ratio < 0.95:
        return "short"
    return "neutral"


def analyze_taker_bias_by_interval(raw: Mapping[str, Any], intervals: list[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for itv in intervals:
        items = (raw.get(itv) or []) if isinstance(raw, Mapping) else []
        last = items[-1] if isinstance(items, list) and items else {}
        if not isinstance(last, Mapping):
            continue
        ratio = _safe_float(last.get("buySellRatio") or 1.0, default=1.0)
        out[itv] = {"labels": {"bias": _taker_bias_from_ratio(ratio)}}
    return out


def _interval_to_horizon(interval: str) -> str:
    if interval in ("5m", "15m", "30m", "1h"):
        return "short_term"
    if interval in ("2h", "4h", "6h", "12h"):
        return "mid_term"
    return "long_term"


def _structure_consensus(open_interest_structure: Mapping[str, Any]) -> Dict[str, str]:
    votes: Dict[str, List[str]] = {"short_term": [], "mid_term": [], "long_term": []}
    for itv, cell in (open_interest_structure or {}).items():
        if not isinstance(cell, dict):
            continue
        hz = _interval_to_horizon(str(itv))
        inf = cell.get("participant_inference") or {}
        if not isinstance(inf, dict):
            continue
        mode = inf.get("positioning_mode")
        conf = inf.get("confidence")
        if conf not in ("medium", "high"):
            continue
        if mode not in ("risk_on", "risk_off", "neutral"):
            continue
        votes[hz].append(str(mode))

    out: Dict[str, str] = {}
    for hz, ms in votes.items():
        if not ms:
            out[hz] = "unclear"
            continue
        counts: Dict[str, int] = {}
        for m in ms:
            counts[m] = counts.get(m, 0) + 1
        ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        if len(ranked) >= 2 and ranked[0][1] == ranked[1][1]:
            out[hz] = "neutral"
        else:
            out[hz] = ranked[0][0]
    return out


async def build_output(exchange: str, symbol: str) -> Dict[str, Any]:
    raw = await read_market_raw(exchange, symbol)
    price_interval = analyze_price_trends_from_klines(raw.get("klines", {}) or {}, PERIODS)
    taker_bias_interval = analyze_taker_bias_by_interval(raw.get("takerLongShortRatio", {}) or {}, PERIODS)

    behavioral = None
    try:
        beh_key = f"behavior:aggTrade:{exchange}:{symbol}"
        beh_raw = await get_redis_client().get(beh_key)
        behavioral = json.loads(beh_raw) if beh_raw else None
    except Exception:
        behavioral = None

    open_interest_structure = analyze_open_interest_hist(
        raw.get("openInterestHist", {}) or {},
        price_interval,
        taker_bias_interval,
        raw.get("24hr", {}) or {},
        behavioral=behavioral,
    )
    open_interest_structure = _coerce_open_interest_structure(open_interest_structure)

    return {
        "symbol": symbol,
        "generated_at": int(time.time() * 1000),
        "open_interest_structure": open_interest_structure,
        "structure_consensus": _structure_consensus(open_interest_structure),
        "evidence": {
            "price": price_interval,
            "taker_bias": taker_bias_interval,
        },
    }


def main(exchange: str = "binance", symbol: str = "ETHUSDT") -> None:
    out = asyncio.run(build_output(exchange, symbol))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
