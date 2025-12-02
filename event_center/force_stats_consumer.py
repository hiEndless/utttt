import asyncio
import json
import os
import time
from typing import Dict, List, Tuple
from redis import asyncio as aioredis
from event_center.config import cfg
from event_center.raw_event import build_raw_event
from event_center.rules import load_rules
import yaml


class ForceStatsConsumer:
    def __init__(self, redis_url: str = cfg.redis_url, scan_interval_s: float = 5.0):
        self.redis = aioredis.from_url(redis_url)
        self.scan_interval_s = scan_interval_s
        self.stream_offsets: Dict[str, str] = {}
        self.last_stats: Dict[str, Dict[str, float]] = {}
        self._running = False
        try:
            self.levels_cfg = load_rules("event_center/event_levels.yml")
        except Exception:
            self.levels_cfg = {"defaults": {}, "levels": {}}
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

    async def _emit_raw(self, symbol: str, ts_ms: int, alert_type: str, details: dict, level: int):
        raw = build_raw_event(
            exchange="binance",
            symbol=symbol,
            account_id="binance_public",
            source="force_stats_consumer",
            event_class="market",
            event_type=alert_type,
            event_level=level,
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
            level = self._map_level(t, d_sell_qty, d_buy_qty, d_sell, d_buy, intensity)
            await self._emit_raw(symbol, ts, t, details, level)

    def _map_level(self, t: str, d_sell_qty: float, d_buy_qty: float, d_sell: int, d_buy: int, intensity: int) -> int:
        cfg = (self.levels_cfg.get("levels") or {}).get(t)
        if not cfg:
            # fallback to existing absolute mapping
            if t in ("force_spike_sell", "force_spike_buy"):
                base_qty = d_sell_qty if t.endswith("sell") else d_buy_qty
                base_cnt = d_sell if t.endswith("sell") else d_buy
                if base_qty >= self.qty_threshold * 5 or base_cnt >= self.count_threshold * 4:
                    return 5
                if base_qty >= self.qty_threshold * 2 or base_cnt >= self.count_threshold * 2:
                    return 4
                if base_qty >= self.qty_threshold or base_cnt >= self.count_threshold:
                    return 3
                return 2
            if t == "force_intensity":
                if intensity >= self.intensity_count_threshold * 4:
                    return 5
                if intensity >= self.intensity_count_threshold * 2:
                    return 4
                if intensity >= self.intensity_count_threshold:
                    return 3
                return 2
            # dominance
            if t.endswith("sell_dominance"):
                ratio = d_sell_qty / max(d_buy_qty, 1e-9)
                base_qty = d_sell_qty
            else:
                ratio = d_buy_qty / max(d_sell_qty, 1e-9)
                base_qty = d_buy_qty
            if ratio >= self.dominance_ratio * 2.5 and base_qty >= self.qty_threshold * 2:
                return 5
            if ratio >= self.dominance_ratio * 1.5 and base_qty >= self.qty_threshold:
                return 4
            if ratio >= self.dominance_ratio and base_qty >= self.qty_threshold / 2:
                return 3
            return 2

        # config-driven mapping (currently absolute thresholds only)
        level = 2
        for m in (cfg.get("metrics") or []):
            name = m.get("name")
            thr = m.get("thresholds", {})
            this_level = 2
            if name == "delta_sell_qty":
                if d_sell_qty >= self.qty_threshold * 5:
                    this_level = max(this_level, 5)
                elif d_sell_qty >= self.qty_threshold * 2:
                    this_level = max(this_level, 4)
                elif d_sell_qty >= self.qty_threshold:
                    this_level = max(this_level, 3)
            elif name == "delta_buy_qty":
                if d_buy_qty >= self.qty_threshold * 5:
                    this_level = max(this_level, 5)
                elif d_buy_qty >= self.qty_threshold * 2:
                    this_level = max(this_level, 4)
                elif d_buy_qty >= self.qty_threshold:
                    this_level = max(this_level, 3)
            elif name == "delta_sell":
                if d_sell >= self.count_threshold * 4:
                    this_level = max(this_level, 5)
                elif d_sell >= self.count_threshold * 2:
                    this_level = max(this_level, 4)
                elif d_sell >= self.count_threshold:
                    this_level = max(this_level, 3)
            elif name == "delta_buy":
                if d_buy >= self.count_threshold * 4:
                    this_level = max(this_level, 5)
                elif d_buy >= self.count_threshold * 2:
                    this_level = max(this_level, 4)
                elif d_buy >= self.count_threshold:
                    this_level = max(this_level, 3)
            elif name == "intensity":
                if intensity >= self.intensity_count_threshold * 4:
                    this_level = max(this_level, 5)
                elif intensity >= self.intensity_count_threshold * 2:
                    this_level = max(this_level, 4)
                elif intensity >= self.intensity_count_threshold:
                    this_level = max(this_level, 3)
            elif name == "dominance_sell_ratio":
                ratio = d_sell_qty / max(d_buy_qty, 1e-9)
                base_qty = d_sell_qty
                if ratio >= self.dominance_ratio * 2.5 and base_qty >= self.qty_threshold * 2:
                    this_level = max(this_level, 5)
                elif ratio >= self.dominance_ratio * 1.5 and base_qty >= self.qty_threshold:
                    this_level = max(this_level, 4)
                elif ratio >= self.dominance_ratio and base_qty >= self.qty_threshold / 2:
                    this_level = max(this_level, 3)
            elif name == "dominance_buy_ratio":
                ratio = d_buy_qty / max(d_sell_qty, 1e-9)
                base_qty = d_buy_qty
                if ratio >= self.dominance_ratio * 2.5 and base_qty >= self.qty_threshold * 2:
                    this_level = max(this_level, 5)
                elif ratio >= self.dominance_ratio * 1.5 and base_qty >= self.qty_threshold:
                    this_level = max(this_level, 4)
                elif ratio >= self.dominance_ratio and base_qty >= self.qty_threshold / 2:
                    this_level = max(this_level, 3)
            level = max(level, this_level)
        return level

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