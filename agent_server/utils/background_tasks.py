import time
import logging
from typing import Dict, List
from agent_server.config import settings
from agent_server.agents.experts.background.market_structure import MarketStructureExpert
from agent_server.agents.experts.background.kline import KLineExpert
from agent_server.agents.experts.background.utils.market_state import market_state_aggregator, save_market_state, has_full_intervals
from agent_server.agents.experts.background.utils.crowd_state_compactor import crowd_state_compactor
from agent_server.utils.http_client import http_client

API_MR_ANALYZE = "/market_raw/analyze"
API_KLINE_READ = "/kline/indicators/read"

logger = logging.getLogger("background")

INDICATOR_INTERVALS = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]
SCHEDULE_SECONDS = {
    "market_structure": 1800,
    "1m": 180,
    "5m": 900,
    "15m": 3600,
    "30m": 7200,
    "1h": 10800,
    "2h": 21600,
    "4h": 43200,
    "1d": 86400,
}


def _period_seconds(interval: str) -> int:
    return int(SCHEDULE_SECONDS.get(interval, 300))


def make_market_structure_task(exchange: str):
    expert = MarketStructureExpert()

    async def run(symbol: str):
        logger.info("bg_task_trigger name=%s time=%s symbol=%s", "market_structure", time.strftime("%Y-%m-%d %H:%M:%S"), symbol)
        base = settings.api_base_url.rstrip("/")
        url = base + API_MR_ANALYZE
        payload = {"exchange": exchange, "symbol": symbol}
        try:
            res = await http_client.request("POST", url, json=payload)
            data = (res or {}).get("data") if isinstance(res, dict) else None
            if not data:
                logger.error("market_structure_api_empty symbol=%s", symbol)
                return
            await expert.run(data, exchange, symbol)
        except Exception as e:
            logger.error("market_structure_api_error %s %s", symbol, e)

    return run


def make_kline_task(exchange: str, interval: str):
    expert = KLineExpert()

    async def run(symbol: str):
        logger.info("bg_task_trigger name=%s interval=%s time=%s symbol=%s", "kline", interval, time.strftime("%Y-%m-%d %H:%M:%S"), symbol)
        base = settings.api_base_url.rstrip("/")
        url = base + API_KLINE_READ
        payload = {"exchange": exchange, "symbol": symbol, "interval": interval}
        try:
            res = await http_client.request("POST", url, json=payload)
            data = (res or {}).get("data") if isinstance(res, dict) else None
            if data is None:
                logger.error("kline_read_api_empty symbol=%s interval=%s", symbol, interval)
                return
            query = {"interval": interval, "symbol": symbol, **(data or {})}
            await expert.run(query, exchange, symbol)
            ms_url = base + "/kline/background/read_multi"
            ms_payload = {"exchange": exchange, "symbol": symbol, "intervals": INDICATOR_INTERVALS}
            try:
                ms_res = await http_client.request("POST", ms_url, json=ms_payload)
                ms_data = (ms_res or {}).get("data") if isinstance(ms_res, dict) else None
                items: List[Dict] = []
                if isinstance(ms_data, dict):
                    for itv, bg in ms_data.items():
                        if isinstance(bg, Dict) and bg:
                            merged = {"interval": itv}
                            merged.update(bg)
                            items.append(merged)
                crowd_url = base + "/crowd_state/read"
                crowd_payload = {"exchange": exchange, "symbol": symbol}
                crowd_res = await http_client.request("POST", crowd_url, json=crowd_payload)
                crowd_raw = (crowd_res or {}).get("data") if isinstance(crowd_res, dict) else None
                crowd_compact = crowd_state_compactor(crowd_raw or {})
                crowd_positioning = (crowd_raw or {}).get("crowd_positioning")
                if has_full_intervals(items):
                    agg = market_state_aggregator(symbol, items, crowd_compact, crowd_positioning)
                    await save_market_state(exchange, symbol, agg)
            except Exception as e:
                logger.error("market_state_aggregate_error %s %s", symbol, e)
        except Exception as e:
            logger.error("kline_read_api_error %s %s %s", symbol, interval, e)

    return run


def build_fetch_plan(exchange: str) -> List[Dict]:
    plan: List[Dict] = []
    plan.append({"name": "market_structure", "fn": make_market_structure_task(exchange), "interval": SCHEDULE_SECONDS["market_structure"]})
    for itv in INDICATOR_INTERVALS:
        plan.append({"name": f"kline_{itv}", "fn": make_kline_task(exchange, itv), "interval": _period_seconds(itv)})
    return plan
