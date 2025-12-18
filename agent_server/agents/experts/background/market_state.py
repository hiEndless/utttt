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


def aggregate_structural_group(backgrounds: List[Dict]) -> Dict:
    trends = [b["trend"] for b in backgrounds]
    structures = [b["structure"]["state"] for b in backgrounds]
    momentums = [b["environment"]["momentum_state"] for b in backgrounds]
    risks = [b["environment"]["risk_state"] for b in backgrounds]

    agreement = _agreement(trends)

    return {
        "direction": _majority_vote(trends),
        "structure": _majority_vote(structures),
        "momentum": _majority_vote(momentums),
        "risk": _majority_vote(risks),
        "conflict": _detect_conflict(trends, momentums),
        "confidence": round(agreement, 2)
    }


def aggregate_micro_term(backgrounds: List[Dict]) -> Dict:
    bg = backgrounds[-1]  # 最近一个即可

    return {
        "state": f"{bg['trend']}_{bg['structure']['state']}",
        "role": "trigger_only",
        "confidence": 0.4
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
                break  # 防止重复归组

    market_state = {
        "symbol": symbol,
        "ts": latest_ts or int(time.time() * 1000),
        "market_state": {}
    }

    for group in GROUP_ORDER:
        items = grouped.get(group)
        if not items:
            continue

        if group == "micro_term":
            market_state["market_state"][group] = aggregate_micro_term(items)
        else:
            agg = aggregate_structural_group(items)

            if group == "long_term":
                agg["veto"] = agg["direction"] == "bearish" and agg["confidence"] >= 0.7

            market_state["market_state"][group] = agg

    return market_state



if __name__ == "__main__":
    import json
    import asyncio
    from agent_server.utils.http_client import http_client
    from agent_server.config import settings

    API_KLINE_READ = "/kline/background/read_multi"

    async def run():
        interval = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]
        url = settings.api_base_url.rstrip("/") + API_KLINE_READ
        payload = {"exchange": "binance", "symbol": "BTCUSDT", "intervals": interval}
        res = await http_client.request("POST", url, json=payload)
        data = (res or {}).get("data") if isinstance(res, dict) else None
        items: List[Dict] = []
        if isinstance(data, dict):
            for itv, bg in data.items():
                if isinstance(bg, dict) and bg:
                    merged = {"interval": itv}
                    merged.update(bg)
                    items.append(merged)
        agg = market_state_aggregator("BTCUSDT", items)
        # print(json.dumps({"aggregate": agg}, ensure_ascii=False))
        print(agg)

    asyncio.run(run())

