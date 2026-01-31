import time
import logging
from typing import Dict, List
from agent_server.config import settings
from agent_server.agents.experts.background.kline import KLineExpert
from agent_server.utils.http_client import http_client

API_KLINE_READ = "/kline/indicators/read"

logger = logging.getLogger("background")

INDICATOR_INTERVALS = ["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]
SCHEDULE_SECONDS = {
    # "1m": 180,
    "5m": 500,
    "15m": 1200,
    "30m": 2000,
    "1h": 4000,
    "2h": 8000,
    "4h": 16000,
    "6h": 24000,
    "12h": 48000,
    "1d": 48000,
}


def _period_seconds(interval: str) -> int:
    return int(SCHEDULE_SECONDS.get(interval, 300))


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
            except Exception as e:
                logger.error("market_state_aggregate_error %s %s", symbol, e)
        except Exception as e:
            logger.error("kline_read_api_error %s %s %s", symbol, interval, e)

    return run


def build_fetch_plan(exchange: str) -> List[Dict]:
    plan: List[Dict] = []
    for itv in INDICATOR_INTERVALS:
        plan.append({"name": f"kline_{itv}", "fn": make_kline_task(exchange, itv), "interval": _period_seconds(itv)})
    return plan
