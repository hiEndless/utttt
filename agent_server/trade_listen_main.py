"""
交易决策监听服务 - 直接监听 l1_events，触发 SignalValidationWorkflow（含交易决策）
"""

import asyncio
import json
import logging
import os
import signal
from datetime import datetime

import redis.asyncio as aioredis
from agent_server.config import settings
from agent_server.agent_workflow.signal_validation_workflow import SignalValidationWorkflow
from agent_server.utils.trade_event_recorder import get_recorder
from agent_server.tools.price_fetcher import get_mark_price_from_redis

TRADE_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(TRADE_LOG_DIR, exist_ok=True)

trade_logger = logging.getLogger("trade_decision")
trade_logger.setLevel(logging.INFO)
trade_logger.propagate = False
trade_handler = logging.FileHandler(
    os.path.join(TRADE_LOG_DIR, f"trade_decision_{datetime.now().strftime('%Y%m%d')}.log"),
    encoding="utf-8",
)
trade_handler.setFormatter(logging.Formatter("%(asctime)s [TRADE] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
trade_logger.addHandler(trade_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("[TRADE] %(message)s"))
trade_logger.addHandler(console_handler)


class TradeL1Listener:
    """监听 l1_events stream，触发交易决策工作流"""

    L1_STREAM = "l1_events"
    DEDUP_TTL = 300
    COOLDOWN_TTL = 10
    MAX_CONCURRENT = 3

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.group = "trade_l1_group"
        self.consumer = "trade_l1_consumer"
        self.event_recorder = get_recorder()
        self.running_workflows = set()

    @staticmethod
    def _j(s):
        try:
            return json.loads(s) if s else {}
        except Exception:
            return {}

    async def _passes_dedup(self, event_id: str) -> bool:
        if not event_id:
            return True
        key = f"trade_l1:dedup:{event_id}"
        try:
            ok = await self.redis.setnx(key, "1")
            if ok:
                await self.redis.expire(key, self.DEDUP_TTL)
            return bool(ok)
        except Exception:
            return True

    async def _is_position_open(self, exchange: str, symbol: str) -> bool:
        try:
            return bool(await self.redis.sismember(f"trading:open_positions:{exchange}", symbol))
        except Exception:
            return False

    async def _passes_cooldown(self, symbol: str) -> bool:
        if not symbol:
            return True
        key = f"trade_l1:cooldown:{symbol}"
        try:
            ok = await self.redis.setnx(key, "1")
            if ok:
                await self.redis.expire(key, self.COOLDOWN_TTL)
            return bool(ok)
        except Exception:
            return True

    async def run(self):
        try:
            await self.redis.xgroup_create(self.L1_STREAM, self.group, id="0", mkstream=True)
        except Exception:
            pass

        trade_logger.info(f"开始监听 {self.L1_STREAM}...")

        while True:
            try:
                res = await self.redis.xreadgroup(
                    self.group,
                    self.consumer,
                    streams={self.L1_STREAM: ">"},
                    count=50,
                    block=5000,
                )
                if not res:
                    continue

                for _stream, entries in res:
                    for entry_id, fields in entries:
                        ev = {k: (v.decode() if isinstance(v, bytes) else str(v)) for k, v in fields.items()}
                        symbol = ev.get("symbol", "").upper()
                        if not symbol:
                            await self.redis.xack(self.L1_STREAM, self.group, entry_id)
                            continue

                        exchange = "binance"
                        event_id = ev.get("event_id", "")
                        if event_id:
                            parts = event_id.split(".")
                            if parts:
                                exchange = parts[0].lower()

                        if not await self._passes_dedup(event_id):
                            await self.redis.xack(self.L1_STREAM, self.group, entry_id)
                            continue
                        if not await self._passes_cooldown(symbol):
                            await self.redis.xack(self.L1_STREAM, self.group, entry_id)
                            continue
                        if await self._is_position_open(exchange, symbol):
                            await self.redis.xack(self.L1_STREAM, self.group, entry_id)
                            continue
                        if len(self.running_workflows) >= self.MAX_CONCURRENT:
                            await self.redis.xack(self.L1_STREAM, self.group, entry_id)
                            continue

                        total_score = float(ev.get("total_score", 0))
                        direction = ev.get("direction", "")
                        market_state = ev.get("market_state", "")
                        hint = ev.get("origin_source_hint", "indicators")
                        tf_hint = ["15m", "30m", "1h"]

                        info = {
                            "route": hint if hint in ("indicators", "mixed") else "indicators",
                            "exchange": exchange,
                            "symbol": symbol,
                            "final_priority": ev.get("result_priority", "low"),
                            "event_id": event_id,
                            "event_type": "l1_aggregated",
                            "timestamp": ev.get("timestamp", ""),
                            "market_state": market_state,
                            "direction": direction,
                            "confidence": "medium" if abs(total_score) >= 1.5 else "low",
                            "confidence_numeric": total_score,
                            "priority_weight": 10,
                            "l1_total_score": total_score,
                            "tf_hint": tf_hint,
                            "analysis_context": {
                                "l1_total_score": total_score,
                                "tf_hint": tf_hint,
                            },
                            "meta": {"origin_source_hint": hint, "source_event_id": event_id},
                            "trade_details": {},
                        }

                        trade_logger.info(f"收到L1事件 | {symbol} | direction={direction} | score={total_score}")

                        mark_price = await get_mark_price_from_redis(exchange, symbol)
                        if mark_price:
                            info["mark_price"] = mark_price

                        self.running_workflows.add(event_id)
                        wf = SignalValidationWorkflow()

                        async def _run_and_cleanup():
                            try:
                                await wf.arun(info)
                            finally:
                                self.running_workflows.discard(event_id)

                        asyncio.create_task(_run_and_cleanup())
                        await self.redis.xack(self.L1_STREAM, self.group, entry_id)

            except Exception as e:
                trade_logger.error(f"处理事件出错: {e}")
                await asyncio.sleep(1)


async def _run():
    password = settings.redis_password
    if isinstance(password, str) and password.strip().lower() in ("none", "null", "undefined", ""):
        password = None
    max_conn = int(os.environ.get("REDIS_MAX_CONNECTIONS", 20))
    pool = aioredis.ConnectionPool(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=password,
        decode_responses=True,
        max_connections=max_conn,
    )
    redis_client = aioredis.Redis(connection_pool=pool)
    listener = TradeL1Listener(redis_client)
    stop = asyncio.Event()

    def _on_sig(*_):
        trade_logger.info("收到停止信号")
        stop.set()

    try:
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, _on_sig)
        loop.add_signal_handler(signal.SIGTERM, _on_sig)
    except NotImplementedError:
        import sys
        signal.signal(signal.SIGINT, lambda s, f: stop.set())
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, lambda s, f: stop.set())

    task = asyncio.create_task(listener.run(), name="trade_l1_listener")
    try:
        while not stop.is_set():
            await asyncio.sleep(0.3)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await redis_client.aclose()
        trade_logger.info("Trade L1 Listener 已停止")


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)
    logging.getLogger("agno").setLevel(logging.CRITICAL)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
