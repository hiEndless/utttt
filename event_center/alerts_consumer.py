import asyncio
import json
import time
from typing import Dict, List, Tuple

from redis import asyncio as aioredis

from event_center.config import cfg


class AlertsConsumer:
    def __init__(self, redis_url: str = cfg.redis_url, scan_interval_s: float = 5.0):
        self.redis = aioredis.from_url(redis_url)
        self.scan_interval_s = scan_interval_s
        self.stream_offsets: Dict[str, str] = {}
        self._running = False

    async def _discover_streams(self):
        try:
            cursor = 0
            keys: List[str] = []
            pattern = "alerts:binance:*"
            while True:
                cursor, batch = await self.redis.scan(cursor=cursor, match=pattern, count=200)
                keys.extend(batch)
                if cursor == 0:
                    break
            for k in keys:
                if k not in self.stream_offsets:
                    self.stream_offsets[k] = "$"
        except Exception:
            pass

    async def _to_raw_event(self, symbol: str, alert_type: str, ts_ms: int, details: dict) -> Dict[str, str]:
        event_id = f"{symbol}:{alert_type}:{ts_ms}"
        payload = {"source": "spike_detector", "type": alert_type, **(details or {})}
        raw = {
            "event_id": event_id,
            "timestamp": str(ts_ms),
            "account_id": "binance_public",
            "symbol": symbol,
            "type": "market_alert",
            "payload": json.dumps(payload, ensure_ascii=False),
        }
        return raw

    async def run(self):
        self._running = True
        print(f"[AlertsConsumer] started, piping alerts:* -> {cfg.raw_stream}")
        last_discover = 0.0
        while self._running:
            now = time.time()
            if now - last_discover > self.scan_interval_s or not self.stream_offsets:
                await self._discover_streams()
                last_discover = now

            if not self.stream_offsets:
                await asyncio.sleep(0.5)
                continue

            try:
                res: List[Tuple[bytes, List[Tuple[bytes, Dict[bytes, bytes]]]]] = await self.redis.xread(
                    streams=self.stream_offsets, count=100, block=3000
                )
            except Exception:
                res = []

            if not res:
                continue

            for stream_name_b, entries in res:
                stream_name = stream_name_b.decode() if isinstance(stream_name_b, (bytes, bytearray)) else str(stream_name_b)
                for entry_id_b, fields_b in entries:
                    entry_id = entry_id_b.decode() if isinstance(entry_id_b, (bytes, bytearray)) else str(entry_id_b)
                    # Update offset for this stream
                    self.stream_offsets[stream_name] = entry_id
                    try:
                        f = {k.decode(): v.decode() for k, v in fields_b.items()}
                        ts_ms = int(f.get("ts", "0") or "0")
                        alert_type = f.get("type") or "unknown"
                        details_s = f.get("details") or "{}"
                        try:
                            details = json.loads(details_s)
                        except Exception:
                            details = {"raw": details_s}
                        # derive symbol from stream name
                        # alerts:binance:{symbol}
                        parts = stream_name.split(":")
                        symbol = parts[-1] if len(parts) >= 3 else "unknown"
                        raw = await self._to_raw_event(symbol, alert_type, ts_ms, details)
                        await self.redis.xadd(cfg.raw_stream, raw)
                        print(f"[AlertsConsumer] -> raw event_id={raw['event_id']} symbol={symbol} type={alert_type}")
                    except Exception as e:
                        print(f"[AlertsConsumer] error stream={stream_name} entry={entry_id} err={e}")


if __name__ == "__main__":
    ac = AlertsConsumer()
    try:
        asyncio.run(ac.run())
    except KeyboardInterrupt:
        pass