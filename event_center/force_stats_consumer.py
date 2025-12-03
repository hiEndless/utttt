import asyncio
import json
import os
import time
from typing import Dict, List, Tuple, Deque
from collections import deque, defaultdict
from redis import asyncio as aioredis
from event_center.config import cfg
from event_center.raw_event import build_raw_event
from event_center.rules import load_rules


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
        self._rw_qty: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=120))
        self._rw_cnt: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=120))
        self.rwq = RollingWindowQuantile(maxlen=120)
        self.session_start: Dict[str, int] = {}
        self.offset_key_prefix = "consumer_offset:force_stats_consumer:"
        self.debounce_key_prefix = "consumer_debounce:force_stats_consumer:"
        self.debounce_seconds = int(os.getenv("FORCE_EVENT_DEBOUNCE_S", "30"))  # 去抖：同类型事件最短间隔（秒）
        self.emit_budget_window_s = int(os.getenv("FORCE_EVENT_BUDGET_WINDOW_S", "60"))  # 配额窗口（秒）
        self.emit_budget_max = int(os.getenv("FORCE_EVENT_BUDGET_MAX", "1"))  # 窗口内允许的事件上限（level<5）
        self._symbol_budget: Dict[str, List[int]] = {}  # 每 symbol 已发事件的时间戳列表
        self.default_qty_threshold = self.qty_threshold
        self.default_count_threshold = self.count_threshold
        self.default_intensity_threshold = self.intensity_count_threshold

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
            for k_b in keys:
                k = k_b.decode() if isinstance(k_b, (bytes, bytearray)) else str(k_b)
                if k not in self.stream_offsets:
                    persist_key = self.offset_key_prefix + k
                    try:
                        off = await self.redis.get(persist_key)
                        if off:
                            self.stream_offsets[k] = off.decode() if isinstance(off, (bytes, bytearray)) else str(off)
                        else:
                            self.stream_offsets[k] = "$"
                    except Exception:
                        self.stream_offsets[k] = "$"
        except Exception:
            pass

    async def _persist_offset(self, stream_name: str, entry_id: str) -> None:
        try:
            await self.redis.set(self.offset_key_prefix + stream_name, entry_id)
        except Exception:
            pass

    async def _emit_raw(self, symbol: str, ts_ms: int, alert_type: str, details: dict, level: int):
        # 先进行配额检查；重大事件（level>=5）越过配额限制
        if not self._budget_check(symbol, ts_ms, level):
            return
        dk = f"{self.debounce_key_prefix}:{symbol}:{alert_type}"
        try:
            set_ok = await self.redis.set(dk, 1, ex=self.debounce_seconds, nx=True)
            if not set_ok:
                return
        except Exception:
            pass
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
        self._budget_record(symbol, ts_ms)  # 记录配额
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
            # start a new session window at first snapshot
            self.session_start[stream_name] = ts
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

        # session start tracking: reset when counters roll back or window exceeds 3 minutes
        reset_counts = (
                cur["SELL"] < int(prev.get("SELL", 0))
                or cur["BUY"] < int(prev.get("BUY", 0))
                or cur["SELL_QTY"] < float(prev.get("SELL_QTY", 0.0))
                or cur["BUY_QTY"] < float(prev.get("BUY_QTY", 0.0))
        )
        start_ts = self.session_start.get(stream_name)
        if start_ts is None or reset_counts or (ts - start_ts) > 180_000:
            start_ts = ts
            self.session_start[stream_name] = start_ts

        # rolling windows for dynamic thresholds
        self._rw_qty[symbol].append(d_buy_qty + d_sell_qty)
        self._rw_cnt[symbol].append(float(d_buy + d_sell))
        self.rwq.append(symbol, d_buy_qty + d_sell_qty)
        self.rwq.append(symbol + ":count", float(d_buy + d_sell))

        dyn_qty = self.rwq.percentile(symbol, 98)
        mean_cnt = self.rwq.mean(symbol + ":count")
        qty_thr = max(self.default_qty_threshold, dyn_qty)
        count_thr = max(self.default_count_threshold, int(mean_cnt) or self.default_count_threshold)
        intensity_thr = max(self.default_intensity_threshold, count_thr * 2)

        targets = []
        if d_sell_qty >= qty_thr or d_sell >= count_thr:
            targets.append("force_spike_sell")
        if d_buy_qty >= qty_thr or d_buy >= count_thr:
            targets.append("force_spike_buy")
        if intensity >= intensity_thr:
            targets.append("force_intensity")
        min_base = max(1.0, qty_thr * 0.1)
        if d_sell_qty >= self.dominance_ratio * max(d_buy_qty, 1e-9) and d_sell_qty >= min_base:
            targets.append("force_sell_dominance")
        if d_buy_qty >= self.dominance_ratio * max(d_sell_qty, 1e-9) and d_buy_qty >= min_base:
            targets.append("force_buy_dominance")
        # enrich details with session info and emit with session start time
        details["start_ts"] = start_ts
        details["last_ts"] = ts
        details["elapsed_ms"] = ts - start_ts
        for t in targets:
            # 强门限：仅在显著强度/主导性满足更高阈值时发出
            if not self._strong_gate(t, d_sell_qty, d_buy_qty, d_sell, d_buy, intensity, qty_thr, count_thr,
                                      intensity_thr, ts - start_ts):
                continue
            level = self._map_level_dyn(t, d_sell_qty, d_buy_qty, d_sell, d_buy, intensity, qty_thr, count_thr,
                                        intensity_thr)
            await self._emit_raw(symbol, start_ts, t, details, level)

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

    def _map_level_dyn(self, t: str, d_sell_qty: float, d_buy_qty: float, d_sell: int, d_buy: int, intensity: int,
                       qty_thr: float, count_thr: int, intensity_thr: int) -> int:
        if t in ("force_spike_sell", "force_spike_buy"):
            base_qty = d_sell_qty if t.endswith("sell") else d_buy_qty
            base_cnt = d_sell if t.endswith("sell") else d_buy
            if base_qty >= qty_thr * 5 or base_cnt >= count_thr * 4:
                return 5
            if base_qty >= qty_thr * 2 or base_cnt >= count_thr * 2:
                return 4
            if base_qty >= qty_thr or base_cnt >= count_thr:
                return 3
            return 2
        if t == "force_intensity":
            if intensity >= intensity_thr * 4:
                return 5
            if intensity >= intensity_thr * 2:
                return 4
            if intensity >= intensity_thr:
                return 3
            return 2
        if t.endswith("sell_dominance"):
            ratio = d_sell_qty / max(d_buy_qty, 1e-9)
            base_qty = d_sell_qty
        else:
            ratio = d_buy_qty / max(d_sell_qty, 1e-9)
            base_qty = d_buy_qty
        if ratio >= self.dominance_ratio * 2.5 and base_qty >= qty_thr * 2:
            return 5
        if ratio >= self.dominance_ratio * 1.5 and base_qty >= qty_thr:
            return 4
        if ratio >= self.dominance_ratio and base_qty >= qty_thr * 0.5:
            return 3
        return 2

    def _strong_gate(self, t: str, d_sell_qty: float, d_buy_qty: float, d_sell: int, d_buy: int, intensity: int,
                      qty_thr: float, count_thr: int, intensity_thr: int, elapsed_ms: int) -> bool:
        # 强门限说明：
        # - 先要求会话已运行至少 10s，避免瞬时尖峰
        # - spike：数量或次数需达到动态阈值的 3 倍
        # - intensity：强度需达到动态阈值的 3 倍
        # - dominance：比值需达到基础支配比的 2 倍，且数量达到动态阈值的 1.5 倍
        if elapsed_ms < 10000:
            return False
        if t in ("force_spike_sell", "force_spike_buy"):
            base_qty = d_sell_qty if t.endswith("sell") else d_buy_qty
            base_cnt = d_sell if t.endswith("sell") else d_buy
            return base_qty >= qty_thr * 3 or base_cnt >= count_thr * 3
        if t == "force_intensity":
            return intensity >= intensity_thr * 3
        if t.endswith("sell_dominance"):
            ratio = d_sell_qty / max(d_buy_qty, 1e-9)
            base_qty = d_sell_qty
        else:
            ratio = d_buy_qty / max(d_sell_qty, 1e-9)
            base_qty = d_buy_qty
        return ratio >= self.dominance_ratio * 2 and base_qty >= qty_thr * 1.5

    def _budget_check(self, symbol: str, ts_ms: int, level: int) -> bool:
        # 分钟配额：窗口内事件数受限；重大事件（level>=5）不受限
        window_ms = self.emit_budget_window_s * 1000
        lst = self._symbol_budget.get(symbol) or []
        lst = [t for t in lst if ts_ms - t <= window_ms]
        self._symbol_budget[symbol] = lst
        if len(lst) >= self.emit_budget_max and level < 5:
            return False
        return True

    def _budget_record(self, symbol: str, ts_ms: int) -> None:
        # 记录一次事件时间戳，用于配额统计
        lst = self._symbol_budget.get(symbol) or []
        lst.append(ts_ms)
        self._symbol_budget[symbol] = lst

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
                stream_name = stream_name_b.decode() if isinstance(stream_name_b, (bytes, bytearray)) else str(
                    stream_name_b)
                for entry_id_b, fields_b in entries:
                    entry_id = entry_id_b.decode() if isinstance(entry_id_b, (bytes, bytearray)) else str(entry_id_b)
                    self.stream_offsets[stream_name] = entry_id
                    await self._persist_offset(stream_name, entry_id)
                    try:
                        await self._handle_entry(stream_name, entry_id, fields_b)
                    except Exception as e:
                        print(f"[ForceStatsConsumer] error stream={stream_name} entry={entry_id} err={e}")


class RollingWindowQuantile:
    def __init__(self, maxlen: int = 120):
        self.maxlen = maxlen
        self.windows: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=self.maxlen))

    def append(self, symbol: str, value: float) -> None:
        w = self.windows[symbol]
        w.append(value)

    def percentile(self, symbol: str, p: float) -> float:
        w = list(self.windows.get(symbol, []))
        if not w:
            return 0.0
        w.sort()
        k = (len(w) - 1) * (p / 100.0)
        f = int(k)
        c = min(f + 1, len(w) - 1)
        if f == c:
            return float(w[int(k)])
        d0 = w[f] * (c - k)
        d1 = w[c] * (k - f)
        return float((d0 + d1))

    def mean(self, symbol: str) -> float:
        w = list(self.windows.get(symbol, []))
        if not w:
            return 0.0
        return sum(w) / len(w)


if __name__ == "__main__":
    c = ForceStatsConsumer()
    try:
        asyncio.run(c.run())
    except KeyboardInterrupt:
        pass