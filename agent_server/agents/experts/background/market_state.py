from typing import Dict, List
from collections import Counter
import time

INTERVAL_GROUPS = {
    "micro_term": {"1m"},
    "short_term": {"5m", "15m"},
    "mid_term": {"30m", "1h", "2h"},
    "long_term": {"4h", "1d"}
}

GROUP_ORDER = ["micro_term", "short_term", "mid_term", "long_term"]

CONFIDENCE_WEIGHT = {
    "micro_term": 0.3,
    "short_term": 0.7,
    "mid_term": 1.0,
    "long_term": 1.2
}

REQUIRED_INTERVALS = {"1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"}


def _majority_vote(values: List[str]) -> str:
    if not values:
        return "unknown"
    return Counter(values).most_common(1)[0][0]


def _agreement(values: List[str]) -> float:
    if not values:
        return 0.0
    c = Counter(values)
    return c.most_common(1)[0][1] / len(values)


def _detect_conflict(trends: List[str], momentums: List[str]) -> str | None:
    if len(set(trends)) > 1:
        return "trend_divergence"
    if "weakening" in momentums and "strengthening" in momentums:
        return "momentum_divergence"
    return None


def detect_long_term_veto(
        *,
        directions: List[str],
        structure: str,
        momentum: str,
        risk: str,
        confidence: float,
        mid_confidence: float | None
) -> bool:
    """
    long_term 一票否决规则
    """

    # 规则 1：方向级对立（4h vs 1d）
    if len(set(directions)) >= 2:
        if "bullish" in directions and "bearish" in directions:
            return True

    # 规则 2：结构 + 动能 同时走坏
    if structure in {"distribution", "breakdown"} and momentum in {"weakening", "exhausted"}:
        return True

    # 规则 3：高风险环境 + 中周期无共识
    if risk == "high" and (mid_confidence is None or mid_confidence < 0.6):
        return True

    # 规则 4：强一致性空头（兜底规则）
    if confidence >= 0.7 and structure != "consolidating" and "bearish" in directions:
        return True

    return False


def aggregate_structural_group(backgrounds: List[Dict], group: str) -> Dict:
    trends = [b["trend"] for b in backgrounds]
    structures = [b["structure"]["state"] for b in backgrounds]
    momentums = [b["environment"]["momentum_state"] for b in backgrounds]
    risks = [b["environment"]["risk_state"] for b in backgrounds]

    agreement = _agreement(trends)
    weight = CONFIDENCE_WEIGHT.get(group, 1.0)

    return {
        "direction": _majority_vote(trends),
        "structure": _majority_vote(structures),
        "momentum": _majority_vote(momentums),
        "risk": _majority_vote(risks),
        "conflict": _detect_conflict(trends, momentums),
        "confidence": round(agreement * weight, 2),
        "_raw_trends": trends  # 👈 新增，仅供 veto 使用
    }


def aggregate_micro_term(backgrounds: List[Dict]) -> Dict:
    bg = backgrounds[-1]
    structure = bg["structure"]["state"]
    proximity = bg["structure"].get("key_level_proximity")
    state = structure
    if proximity:
        state = f"{structure}_{proximity}"

    return {
        "state": state,
        "role": "trigger_only",
        "confidence": CONFIDENCE_WEIGHT["micro_term"]
    }


def market_state_aggregator(symbol: str, kline_backgrounds: List[Dict]) -> Dict:
    grouped: Dict[str, List[Dict]] = {k: [] for k in INTERVAL_GROUPS}
    latest_ts = 0

    for bg in kline_backgrounds:
        interval = bg.get("interval")
        latest_ts = max(latest_ts, bg.get("ts", 0))

        for group, intervals in INTERVAL_GROUPS.items():
            if interval in intervals:
                grouped[group].append(bg)
                break

    market_state = {
        "symbol": symbol,
        "ts": latest_ts or int(time.time() * 1000),
        "market_state": {}
    }

    mid_confidence: float | None = None

    for group in GROUP_ORDER:
        items = grouped.get(group)
        if not items:
            continue

        if group == "micro_term":
            market_state["market_state"][group] = aggregate_micro_term(items)
            continue

        agg = aggregate_structural_group(items, group)

        if group == "mid_term":
            mid_confidence = agg["confidence"]

        if group == "long_term":
            agg["veto"] = detect_long_term_veto(
                directions=agg.get("_raw_trends", []),
                structure=agg["structure"],
                momentum=agg["momentum"],
                risk=agg["risk"],
                confidence=agg["confidence"],
                mid_confidence=mid_confidence
            )
            agg.pop("_raw_trends", None)  # 清理内部字段

        market_state["market_state"][group] = agg

    return market_state


async def save_market_state(exchange: str, symbol: str, market_state: Dict) -> None:
    from agent_server.utils.redis_client import RedisClient
    client = RedisClient()
    key = f"background:{exchange}:{symbol}:market_state"
    await client.set_json(key, market_state)

def has_full_intervals(kline_backgrounds: List[Dict]) -> bool:
    present = set()
    for bg in kline_backgrounds:
        itv = bg.get("interval")
        if itv:
            present.add(itv)
    return REQUIRED_INTERVALS.issubset(present)

if __name__ == "__main__":
    import json
    import asyncio
    import os
    import sys
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from agent_server.utils.http_client import http_client
    from agent_server.config import settings

    API_KLINE_READ = "/kline/background/read_multi"


    async def run():
        interval = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]
        url = settings.api_base_url.rstrip("/") + API_KLINE_READ
        payload = {"exchange": "binance", "symbol": "BTCUSDT", "intervals": interval}
        try:
            res = await http_client.request("POST", url, json=payload)
            data = (res or {}).get("data") if isinstance(res, dict) else None
            items: List[Dict] = []
            if isinstance(data, dict):
                for itv, bg in data.items():
                    if isinstance(bg, dict) and bg:
                        merged = {"interval": itv}
                        merged.update(bg)
                        items.append(merged)
            if not has_full_intervals(items):
                return
            agg = market_state_aggregator("BTCUSDT", items)
            await save_market_state("binance", "BTCUSDT", agg)
        finally:
            await http_client.close()

    asyncio.run(run())
