import time
import logging
from typing import Dict, List
from agent_server.config import settings
from agent_server.agents.experts.background.market_structure import MarketStructureExpert
from agent_server.agents.experts.background.kline import KLineExpert
from agent_server.utils.http_client import http_client

API_MR_ANALYZE = "/market_raw/analyze"
API_KLINE_READ = "/kline/indicators/read"

logger = logging.getLogger("background")

INDICATOR_INTERVALS = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]
DEFAULT_RATE_LIMITS = {
    "1m": 60,
    "5m": 150,
    "15m": 300,
    "30m": 600,
    "1h": 900,
    "2h": 1800,
    "4h": 3600,
    "1d": 43200,
}


def _period_seconds(interval: str) -> int:
    return int(settings.rate_limits_seconds.get(interval, DEFAULT_RATE_LIMITS.get(interval, 300)))


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
        print(url)
        payload = {"exchange": exchange, "symbol": symbol, "interval": interval}
        print(payload)
        try:
            res = await http_client.request("POST", url, json=payload)
            data = (res or {}).get("data") if isinstance(res, dict) else None
            if data is None:
                logger.error("kline_read_api_empty symbol=%s interval=%s", symbol, interval)
                return
            query = {"interval": interval, "symbol": symbol, **(data or {})}
            await expert.run(query, exchange, symbol)
        except Exception as e:
            logger.error("kline_read_api_error %s %s %s", symbol, interval, e)

    return run


def build_fetch_plan(exchange: str) -> List[Dict]:
    plan: List[Dict] = []
    plan.append({"name": "market_structure", "fn": make_market_structure_task(exchange), "interval": _period_seconds("5m")})
    for itv in INDICATOR_INTERVALS:
        plan.append({"name": f"kline_{itv}", "fn": make_kline_task(exchange, itv), "interval": _period_seconds(itv)})
    return plan
