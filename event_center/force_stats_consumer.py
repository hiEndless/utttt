import asyncio
import json
import os
import time
from typing import Dict, List, Tuple
from redis import asyncio as aioredis
from event_center.config import cfg
from event_center.raw_event import build_raw_event


class ForceStatsConsumer:
    def __init__(self, redis_url: str = cfg.redis_url, scan_interval_s: float = 5.0):
        self.redis = aioredis.from_url(redis_url)
        self.scan_interval_s = scan_interval_s
        self.stream_offsets: Dict[str, str] = {}
        self.last_stats: Dict[str, Dict[str, float]] = {}
        self._running = False
        self.qty_threshold = float(os.getenv("FORCE_SPIKE_QTY_THRESHOLD", "1000"))
        self.count_threshold = int(os.getenv("FORCE_SPIKE_COUNT_THRESHOLD", "3"))
        self.intensity_count_threshold = int(os.getenv("FORCE_INTENSITY_COUNT_THRESHOLD", "5"))
        self.dominance_ratio = float(os.getenv("FORCE_DOMINANCE_RATIO", "2.0"))

    async def _discover_streams(self):
        try:
            cursor = 0
            keys: List[str] = []
            pattern = "force_stats_stream:binance:*"
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

    async def _emit_alert(self, symbol: str, ts_ms: int, alert_type: str, details: dict):
        stream = f"alerts:binance:{symbol}"
        payload = {
            "ts": ts_ms,
            "type": alert_type,
            "details": json.dumps(details, ensure_ascii=False),
        }
        await self.redis.xadd(stream, payload)
        print(f"[ForceStatsConsumer] -> alert symbol={symbol} type={alert_type} ts={ts_ms}")

    async def _emit_raw(self, symbol: str, ts_ms: int, alert_type: str, details: dict):
        raw = build_raw_event(
            exchange="binance",
            symbol=symbol,
            account_id="binance_public",
            source="force_stats_consumer",
            event_class="market",
            event_type=alert_type,
            event_level=2,
            timestamp_ms=ts_ms,
            payload=details,
        )
        await self.redis.xadd(cfg.raw_stream, raw)
        print(f"[ForceStatsConsumer] -> raw event_id={raw['event_id']} symbol={symbol} type={alert_type}")

    async def _handle_entry(self, stream_name: str, entry_id: str, fields_b: Dict[bytes, bytes]):
        f = {k.decode(): v.decode() for k, v in fields_b.items()}
        parts = stream_name.split(":")
        symbol = parts[-1] if len(parts) >= 3 else "unknown"
        try:
            ts = int(f.get("ts", "0") or "0")
        except Exception:
            ts = int(time.time() * 1000)
        def _to_float(x):
            try:
                return float(x)
            except Exception:
                return 0.0
        def _to_int(x):
            try:
                return int(x)
            except Exception:
                try:
                    return int(float(x))
                except Exception:
                    return 0
        cur = {
            "SELL": _to_int(f.get("SELL", "0")),
            "BUY": _to_int(f.get("BUY", "0")),
            "SELL_QTY": _to_float(f.get("SELL_QTY", "0")),
            "BUY_QTY": _to_float(f.get("BUY_QTY", "0")),
            "ts": ts,
        }

        prev = self.last_stats.get(stream_name)
        self.last_stats[stream_name] = cur
        if prev is None:
            return

        d_sell = max(0, cur["SELL"] - int(prev.get("SELL", 0)))
        d_buy = max(0, cur["BUY"] - int(prev.get("BUY", 0)))
        d_sell_qty = max(0.0, cur["SELL_QTY"] - float(prev.get("SELL_QTY", 0.0)))
        d_buy_qty = max(0.0, cur["BUY_QTY"] - float(prev.get("BUY_QTY", 0.0)))
        intensity = d_sell + d_buy

        details = {
            "delta_sell": d_sell,
            "delta_buy": d_buy,
            "delta_sell_qty": d_sell_qty,
            "delta_buy_qty": d_buy_qty,
            "intensity": intensity,
            "totals": {
                "SELL": cur["SELL"],
                "BUY": cur["BUY"],
                "SELL_QTY": cur["SELL_QTY"],
                "BUY_QTY": cur["BUY_QTY"],
            },
        }

        targets = []
        if d_sell_qty >= self.qty_threshold or d_sell >= self.count_threshold:
            targets.append("force_spike_sell")
        if d_buy_qty >= self.qty_threshold or d_buy >= self.count_threshold:
            targets.append("force_spike_buy")
        if intensity >= self.intensity_count_threshold:
            targets.append("force_intensity")
        if d_sell_qty >= self.dominance_ratio * max(d_buy_qty, 1e-9) and d_sell_qty >= self.qty_threshold / 2:
            targets.append("force_sell_dominance")
        if d_buy_qty >= self.dominance_ratio * max(d_sell_qty, 1e-9) and d_buy_qty >= self.qty_threshold / 2:
            targets.append("force_buy_dominance")
        for t in targets:
            await self._emit_raw(symbol, ts, t, details)

    async def run(self):
        self._running = True
        print("[ForceStatsConsumer] started, piping force_stats_stream:* -> output")
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
                    streams=self.stream_offsets, count=200, block=3000
                )
            except Exception:
                res = []

            if not res:
                continue

            for stream_name_b, entries in res:
                stream_name = stream_name_b.decode() if isinstance(stream_name_b, (bytes, bytearray)) else str(stream_name_b)
                for entry_id_b, fields_b in entries:
                    entry_id = entry_id_b.decode() if isinstance(entry_id_b, (bytes, bytearray)) else str(entry_id_b)
                    self.stream_offsets[stream_name] = entry_id
                    try:
                        await self._handle_entry(stream_name, entry_id, fields_b)
                    except Exception as e:
                        print(f"[ForceStatsConsumer] error stream={stream_name} entry={entry_id} err={e}")


if __name__ == "__main__":
    c = ForceStatsConsumer()
    try:
        asyncio.run(c.run())
    except KeyboardInterrupt:
        pass