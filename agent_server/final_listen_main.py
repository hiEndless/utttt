import asyncio
import logging
import signal
import json
import redis.asyncio as aioredis
from agent_server.config import settings


class RouterFinalListener:
    FINAL_STREAM = "final_events"
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
        self.final_stream = self.FINAL_STREAM
        self.group = "agent_final_router_group"
        self.consumer = "agent_final_router"

    @staticmethod
    def _j(s: str):
        try:
            return json.loads(s) if s else {}
        except Exception:
            return {}

    async def run(self):
        try:
            await self.redis.xgroup_create(self.final_stream, self.group, id="0", mkstream=True)
        except Exception:
            pass
        while True:
            res = await self.redis.xreadgroup(self.group, self.consumer, streams={self.final_stream: ">"}, count=50, block=5000)
            if not res:
                continue
            for _stream_name, entries in res:
                for entry_id, fields in entries:
                    ev = {k: (v if isinstance(v, str) else str(v)) for k, v in fields.items()}
                    meta = self._j(ev.get("meta") or "{}")
                    ac = self._j(ev.get("analysis_context") or "{}")
                    st = self._j(ev.get("structure") or "{}")
                    hint = meta.get("origin_source_hint") or (ac.get("provenance") or {}).get("origin_source_hint") or "unknown"
                    exchange = ev.get("exchange") or meta.get("exchange") or (ac.get("provenance") or {}).get("exchange") or st.get("exchange")
                    if not exchange:
                        acc_id = ev.get("account_id") or ""
                        if acc_id:
                            exchange = (acc_id.split("_")[0] or "").lower()
                    if not exchange:
                        se_id = meta.get("source_event_id") or ""
                        if se_id:
                            exchange = (se_id.split(".")[0] or "").lower()
                    if not exchange and hint in {"binance", "okx", "bybit", "bitget", "kraken", "coinbase", "huobi", "gate", "mexc"}:
                        exchange = hint
                    symbol = ev.get("symbol") or ""
                    fp = ev.get("final_priority") or "low"
                    info = {
                        "route": hint,
                        "exchange": exchange or "",
                        "symbol": symbol,
                        "final_priority": fp,
                        "event_id": ev.get("event_id") or "",
                        "market_state": st.get("market_state"),
                        "direction": st.get("direction"),
                        "confidence": st.get("confidence"),
                        "confidence_numeric": st.get("confidence_numeric"),
                        "priority_weight": st.get("priority_weight"),
                        "l1_total_score": ac.get("l1_total_score"),
                        "tf_hint": ac.get("tf_hint"),
                    }
                    try:
                        print("[FinalRouter] dispatch", json.dumps(info, ensure_ascii=False))
                    except Exception:
                        print("[FinalRouter] dispatch", info)
                    await self.redis.xack(self.final_stream, self.group, entry_id)


async def _run():
    redis = aioredis.Redis(host=settings.redis_host, password=settings.redis_password, port=settings.redis_port, db=settings.redis_db, decode_responses=True)
    listener = RouterFinalListener(redis)
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _on_sig(*_):
        logging.getLogger("final").info("received_stop_signal")
        stop.set()

    loop.add_signal_handler(signal.SIGINT, _on_sig)
    loop.add_signal_handler(signal.SIGTERM, _on_sig)
    task = asyncio.create_task(listener.run(), name="final_events_router")
    try:
        while not stop.is_set():
            await asyncio.sleep(0.3)
    finally:
        try:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        except Exception:
            pass
        await redis.aclose()


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    asyncio.run(_run())


if __name__ == "__main__":
    main()
