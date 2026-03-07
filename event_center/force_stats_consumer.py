import asyncio
import json
import os
import time
from typing import Dict, List, Tuple, Deque
from collections import deque, defaultdict
from redis import asyncio as aioredis
from event_center.config import cfg
from event_center.pipeline.raw_event import build_raw_event
from event_center.rules import load_rules


class ForceStatsConsumer:
    def __init__(self, redis_url: str = cfg.redis_url, scan_interval_s: float = 5.0, exchange: str = "binance"):
        self.redis = aioredis.from_url(redis_url)
        self.scan_interval_s = scan_interval_s
        self.exchange = exchange
        self.stream_offsets: Dict[str, str] = {}
        self.last_stats: Dict[str, Dict[str, float]] = {}
        self._running = False
        try:
            self.levels_cfg = load_rules("event_center/event_levels.yml")
        except Exception:
            self.levels_cfg = {"defaults": {}, "levels": {}}
        self.use_notional = (os.getenv("FORCE_USE_NOTIONAL", "1").lower() in ("1", "true", "yes", "y", "on"))
        self.qty_threshold = float(os.getenv("FORCE_SPIKE_QTY_THRESHOLD", "1000"))
        self.notional_threshold = float(os.getenv("FORCE_SPIKE_NOTIONAL_THRESHOLD", "2000"))
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
        self.emit_budget_window_s = int(os.getenv("FORCE_EVENT_BUDGET_WINDOW_S", "30"))  # 配额窗口（秒）
        self.emit_budget_max = int(os.getenv("FORCE_EVENT_BUDGET_MAX", "1"))  # 窗口内允许的事件上限（level<5）
        self._symbol_budget: Dict[str, List[int]] = {}  # 每 symbol 已发事件的时间戳列表
        self.default_qty_threshold = self.notional_threshold if self.use_notional else self.qty_threshold
        self.default_count_threshold = self.count_threshold
        self.default_intensity_threshold = self.intensity_count_threshold
        self.gate_window_ms = int(os.getenv("FORCE_GATE_WINDOW_MS", "180000"))  # 强门限评估窗口（毫秒），默认3分钟
        self._agg: Dict[str, Deque[Tuple[int, int, int, float, float]]] = defaultdict(lambda: deque(maxlen=600))  # (ts, d_sell, d_buy, d_sell_metric, d_buy_metric)
        self.total_count_threshold_sell = int(os.getenv("FORCE_TOTAL_SELL_COUNT_THRESHOLD", "20"))
        self.total_count_threshold_buy = int(os.getenv("FORCE_TOTAL_BUY_COUNT_THRESHOLD", "20"))
        self.rebound_streak = int(os.getenv("FORCE_REBOUND_STREAK", "3"))
        self.rebound_window_ms = int(os.getenv("FORCE_REBOUND_WINDOW_MS", "20000"))
        self._last_dominant_side: Dict[str, str] = {}
        self._last_dominance_ts: Dict[str, int] = {}
        self._rebound_streak: Dict[str, Dict[str, int]] = defaultdict(lambda: {"buy": 0, "sell": 0})
        self._price_cache: Dict[str, Tuple[float, int]] = {}  # symbol -> (price, fetched_at_ms)
        self.min_signal_strength = float(os.getenv("FORCE_MIN_SIGNAL_STRENGTH", "2.2"))
        self.strong_gate_min_session_ms = int(os.getenv("FORCE_STRONG_GATE_MIN_SESSION_MS", "500"))
        self.strong_gate_spike_mult = float(os.getenv("FORCE_STRONG_GATE_SPIKE_MULT", "1.5"))
        self.strong_gate_intensity_mult = float(os.getenv("FORCE_STRONG_GATE_INTENSITY_MULT", "2.0"))
        self.strong_gate_dominance_ratio_mult = float(os.getenv("FORCE_STRONG_GATE_DOM_RATIO_MULT", "1.5"))
        self.strong_gate_dominance_qty_mult = float(os.getenv("FORCE_STRONG_GATE_DOM_QTY_MULT", "1.2"))

    async def _discover_streams(self):
        try:
            cursor = 0
            keys: List[str] = []
            pattern = f"force_stats_stream:{self.exchange}:*"
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

    async def _emit_raw(self, symbol: str, ts_ms: int, alert_type: str, payload: dict, level: int):
        level = max(2, int(level))
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
            exchange=self.exchange,
            symbol=symbol,
            account_id=f"{self.exchange}_public",
            source="force_stats_consumer",
            event_class="market",
            event_type=alert_type,
            event_level=level,
            timestamp_ms=ts_ms,
            payload=payload,
        )
        await self.redis.xadd(cfg.raw_stream, raw)
        self._budget_record(symbol, ts_ms)  # 记录配额
        print(f"[ForceStatsConsumer] -> raw event_id={raw['event_id']} symbol={symbol} type={alert_type}")

    async def _get_price(self, symbol: str, now_ms: int) -> float:
        cached = self._price_cache.get(symbol)
        if cached:
            px, fetched_at = cached
            if now_ms - fetched_at <= 1000 and px > 0:
                return px
        key = f"price:{self.exchange}:{symbol}"
        try:
            px_s = await self.redis.hget(key, "price")
            if px_s is None:
                return cached[0] if cached else 0.0
            px = float(px_s.decode() if isinstance(px_s, (bytes, bytearray)) else px_s)
            if px > 0:
                self._price_cache[symbol] = (px, now_ms)
            return px
        except Exception:
            return cached[0] if cached else 0.0

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
        px = await self._get_price(symbol, ts)
        d_sell_metric = d_sell_qty
        d_buy_metric = d_buy_qty
        tot_sell_metric = cur["SELL_QTY"]
        tot_buy_metric = cur["BUY_QTY"]
        if self.use_notional and px > 0:
            d_sell_metric = d_sell_qty * px
            d_buy_metric = d_buy_qty * px
            tot_sell_metric = cur["SELL_QTY"] * px
            tot_buy_metric = cur["BUY_QTY"] * px

        # 追加到聚合窗口，用于按时间窗计算累计指标
        self._agg[symbol].append((ts, d_sell, d_buy, d_sell_metric, d_buy_metric))

        details = {
            "delta_sell": d_sell,
            "delta_buy": d_buy,
            "delta_sell_qty": d_sell_qty,
            "delta_buy_qty": d_buy_qty,
            "price": px,
            "delta_sell_value": d_sell_metric if self.use_notional else 0.0,
            "delta_buy_value": d_buy_metric if self.use_notional else 0.0,
            "intensity": intensity,
            "totals": {
                "SELL": cur["SELL"],
                "BUY": cur["BUY"],
                "SELL_QTY": cur["SELL_QTY"],
                "BUY_QTY": cur["BUY_QTY"],
                "SELL_VALUE": tot_sell_metric if self.use_notional else 0.0,
                "BUY_VALUE": tot_buy_metric if self.use_notional else 0.0,
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
        self._rw_qty[symbol].append(d_buy_metric + d_sell_metric)
        self._rw_cnt[symbol].append(float(d_buy + d_sell))
        self.rwq.append(symbol, d_buy_metric + d_sell_metric)
        self.rwq.append(symbol + ":count", float(d_buy + d_sell))

        dyn_qty = self.rwq.percentile(symbol, 98)
        mean_cnt = self.rwq.mean(symbol + ":count")
        qty_thr = max(self.default_qty_threshold, dyn_qty)
        count_thr = max(self.default_count_threshold, int(mean_cnt) or self.default_count_threshold)
        intensity_thr = max(self.default_intensity_threshold, count_thr * 2)

        targets = []
        # immediate triggers
        if d_sell_metric >= qty_thr or d_sell >= count_thr:
            targets.append("force_spike_sell")
        if d_buy_metric >= qty_thr or d_buy >= count_thr:
            targets.append("force_spike_buy")
        if intensity >= intensity_thr:
            targets.append("force_intensity")
        min_base = max(1.0, qty_thr * 0.1)
        if d_sell_metric >= self.dominance_ratio * max(d_buy_metric, 1e-9) and d_sell_metric >= min_base:
            targets.append("force_sell_dominance")
        if d_buy_metric >= self.dominance_ratio * max(d_sell_metric, 1e-9) and d_buy_metric >= min_base:
            targets.append("force_buy_dominance")
        # window/cumulative derived triggers (enable for +1 increments)
        # compute window sums
        dq = self._agg.get(symbol) or deque()
        sell_cnt_sum = sum(sc for _, sc, __, ___, ____ in dq)
        buy_cnt_sum = sum(bc for _, __, bc, ___, ____ in dq)
        sell_qty_sum = sum(sq for _, __, ___, sq, ____ in dq)
        buy_qty_sum = sum(bq for _, __, ___, ____, bq in dq)
        if sell_qty_sum >= qty_thr * 3 or sell_cnt_sum >= count_thr * 6 or cur["SELL"] >= count_thr * 6:
            targets.append("force_spike_sell")
        if buy_qty_sum >= qty_thr * 3 or buy_cnt_sum >= count_thr * 6 or cur["BUY"] >= count_thr * 6:
            targets.append("force_spike_buy")
        if (sell_cnt_sum + buy_cnt_sum) >= intensity_thr * 6 or (cur["SELL"] + cur["BUY"]) >= intensity_thr * 6:
            targets.append("force_intensity")
        # dominance via counts as fallback
        if buy_cnt_sum > 0 and sell_cnt_sum / max(buy_cnt_sum, 1) >= max(self.dominance_ratio, 3.0) and sell_cnt_sum >= count_thr * 6:
            targets.append("force_sell_dominance")
        if sell_cnt_sum > 0 and buy_cnt_sum / max(sell_cnt_sum, 1) >= max(self.dominance_ratio, 3.0) and buy_cnt_sum >= count_thr * 6:
            targets.append("force_buy_dominance")
        # totals-based immediate triggers and trend tracking
        if cur["SELL"] >= self.total_count_threshold_sell:
            targets.append("force_spike_sell")
            self._last_dominant_side[symbol] = "sell"
            self._last_dominance_ts[symbol] = ts
        if cur["BUY"] >= self.total_count_threshold_buy:
            targets.append("force_spike_buy")
            self._last_dominant_side[symbol] = "buy"
            self._last_dominance_ts[symbol] = ts
        # rebound detection based on consecutive opposite increments
        if d_buy > 0:
            self._rebound_streak[symbol]["buy"] += 1
        else:
            self._rebound_streak[symbol]["buy"] = 0
        if d_sell > 0:
            self._rebound_streak[symbol]["sell"] += 1
        else:
            self._rebound_streak[symbol]["sell"] = 0
        last_side = self._last_dominant_side.get(symbol)
        last_ts = self._last_dominance_ts.get(symbol, 0)
        if last_side == "sell" and ts - last_ts <= self.rebound_window_ms and self._rebound_streak[symbol]["buy"] >= self.rebound_streak:
            targets.append("force_rebound_buy")
        if last_side == "buy" and ts - last_ts <= self.rebound_window_ms and self._rebound_streak[symbol]["sell"] >= self.rebound_streak:
            targets.append("force_rebound_sell")
        # enrich details with session info and emit with session start time
        details["start_ts"] = start_ts
        details["last_ts"] = ts
        details["elapsed_ms"] = ts - start_ts
        for t in targets:
            # 强门限：仅在显著强度/主导性满足更高阈值时发出
            if not self._strong_gate(symbol, ts, t, d_sell_metric, d_buy_metric, d_sell, d_buy, intensity, qty_thr, count_thr,
                                      intensity_thr, ts - start_ts, cur["SELL"], cur["BUY"], tot_sell_metric, tot_buy_metric):
                continue
            level = self._map_level_dyn(t, d_sell_metric, d_buy_metric, d_sell, d_buy, intensity, qty_thr, count_thr,
                                        intensity_thr)
            level = max(2, int(level))
            # 构建摘要以适配管线
            if t in ("force_spike_buy", "force_buy_dominance", "force_rebound_buy"):
                direction = "bullish"
            elif t in ("force_spike_sell", "force_sell_dominance", "force_rebound_sell"):
                direction = "bearish"
            elif t == "force_intensity":
                direction = "bullish" if (d_buy_metric + d_buy) >= (d_sell_metric + d_sell) else "bearish"
            else:
                direction = "neutral"
            try:
                if t in ("force_spike_buy", "force_spike_sell"):
                    base_qty = d_sell_metric if t.endswith("sell") else d_buy_metric
                    base_cnt = d_sell if t.endswith("sell") else d_buy
                    strength = max(base_qty / max(qty_thr, 1e-9), base_cnt / max(count_thr, 1e-9))
                elif t == "force_intensity":
                    strength = intensity / max(intensity_thr, 1e-9)
                elif t in ("force_buy_dominance", "force_sell_dominance"):
                    ratio = (d_sell_metric / max(d_buy_metric, 1e-9)) if t.endswith("sell") else (d_buy_metric / max(d_sell_metric, 1e-9))
                    strength = ratio / max(self.dominance_ratio, 1e-9)
                else:
                    strength = 2.0
            except Exception:
                strength = float(level)
            strength = max(float(strength), float(self.min_signal_strength))
            payload = {
                "summary": {
                    "direction": direction,
                    "signal_strength": float(strength),
                    "primary_tf": "1m",
                },
                "evidence": {
                    "plugins": [{"name": t, "tfs": ["1m"]}],
                },
                "details": details,
            }
            await self._emit_raw(symbol, ts, t, payload, level)

    def _map_level(self, t: str, d_sell_qty: float, d_buy_qty: float, d_sell: int, d_buy: int, intensity: int) -> int:
        cfg = (self.levels_cfg.get("levels") or {}).get(t)
        if not cfg:
            # fallback to existing absolute mapping
            if t in ("force_spike_sell", "force_spike_buy"):
                base_qty = d_sell_qty if t.endswith("sell") else d_buy_qty
                base_cnt = d_sell if t.endswith("sell") else d_buy
                if base_qty >= self.qty_threshold * 5 or base_cnt >= self.count_threshold * 4:
                    return 4
                if base_qty >= self.qty_threshold * 2 or base_cnt >= self.count_threshold * 2:
                    return 3
                if base_qty >= self.qty_threshold or base_cnt >= self.count_threshold:
                    return 2
                return 1
            if t == "force_intensity":
                if intensity >= self.intensity_count_threshold * 4:
                    return 4
                if intensity >= self.intensity_count_threshold * 2:
                    return 3
                if intensity >= self.intensity_count_threshold:
                    return 2
                return 1
            # dominance
            if t.endswith("sell_dominance"):
                ratio = d_sell_qty / max(d_buy_qty, 1e-9)
                base_qty = d_sell_qty
            else:
                ratio = d_buy_qty / max(d_sell_qty, 1e-9)
                base_qty = d_buy_qty
            if ratio >= self.dominance_ratio * 2.5 and base_qty >= self.qty_threshold * 2:
                return 4
            if ratio >= self.dominance_ratio * 1.5 and base_qty >= self.qty_threshold:
                return 3
            if ratio >= self.dominance_ratio and base_qty >= self.qty_threshold / 2:
                return 2
            return 1

        # config-driven mapping (currently absolute thresholds only)
        level = 1
        for m in (cfg.get("metrics") or []):
            name = m.get("name")
            thr = m.get("thresholds", {})
            this_level = 1
            if name == "delta_sell_qty":
                if d_sell_qty >= self.qty_threshold * 5:
                    this_level = max(this_level, 4)
                elif d_sell_qty >= self.qty_threshold * 2:
                    this_level = max(this_level, 3)
                elif d_sell_qty >= self.qty_threshold:
                    this_level = max(this_level, 2)
            elif name == "delta_buy_qty":
                if d_buy_qty >= self.qty_threshold * 5:
                    this_level = max(this_level, 4)
                elif d_buy_qty >= self.qty_threshold * 2:
                    this_level = max(this_level, 3)
                elif d_buy_qty >= self.qty_threshold:
                    this_level = max(this_level, 2)
            elif name == "delta_sell":
                if d_sell >= self.count_threshold * 4:
                    this_level = max(this_level, 4)
                elif d_sell >= self.count_threshold * 2:
                    this_level = max(this_level, 3)
                elif d_sell >= self.count_threshold:
                    this_level = max(this_level, 2)
            elif name == "delta_buy":
                if d_buy >= self.count_threshold * 4:
                    this_level = max(this_level, 4)
                elif d_buy >= self.count_threshold * 2:
                    this_level = max(this_level, 3)
                elif d_buy >= self.count_threshold:
                    this_level = max(this_level, 2)
            elif name == "intensity":
                if intensity >= self.intensity_count_threshold * 4:
                    this_level = max(this_level, 4)
                elif intensity >= self.intensity_count_threshold * 2:
                    this_level = max(this_level, 3)
                elif intensity >= self.intensity_count_threshold:
                    this_level = max(this_level, 2)
            elif name == "dominance_sell_ratio":
                ratio = d_sell_qty / max(d_buy_qty, 1e-9)
                base_qty = d_sell_qty
                if ratio >= self.dominance_ratio * 2.5 and base_qty >= self.qty_threshold * 2:
                    this_level = max(this_level, 4)
                elif ratio >= self.dominance_ratio * 1.5 and base_qty >= self.qty_threshold:
                    this_level = max(this_level, 3)
                elif ratio >= self.dominance_ratio and base_qty >= self.qty_threshold / 2:
                    this_level = max(this_level, 2)
            elif name == "dominance_buy_ratio":
                ratio = d_buy_qty / max(d_sell_qty, 1e-9)
                base_qty = d_buy_qty
                if ratio >= self.dominance_ratio * 2.5 and base_qty >= self.qty_threshold * 2:
                    this_level = max(this_level, 4)
                elif ratio >= self.dominance_ratio * 1.5 and base_qty >= self.qty_threshold:
                    this_level = max(this_level, 3)
                elif ratio >= self.dominance_ratio and base_qty >= self.qty_threshold / 2:
                    this_level = max(this_level, 2)
            level = max(level, this_level)
        return level

    def _map_level_dyn(self, t: str, d_sell_qty: float, d_buy_qty: float, d_sell: int, d_buy: int, intensity: int,
                       qty_thr: float, count_thr: int, intensity_thr: int) -> int:
        if t in ("force_spike_sell", "force_spike_buy"):
            base_qty = d_sell_qty if t.endswith("sell") else d_buy_qty
            base_cnt = d_sell if t.endswith("sell") else d_buy
            if base_qty >= qty_thr * 5 or base_cnt >= count_thr * 4:
                return 4
            if base_qty >= qty_thr * 2 or base_cnt >= count_thr * 2:
                return 3
            if base_qty >= qty_thr or base_cnt >= count_thr:
                return 2
            return 2
        if t == "force_intensity":
            if intensity >= intensity_thr * 4:
                return 4
            if intensity >= intensity_thr * 2:
                return 3
            if intensity >= intensity_thr:
                return 2
            return 2
        if t == "force_rebound_buy" or t == "force_rebound_sell":
            return 2
        if t.endswith("sell_dominance"):
            ratio = d_sell_qty / max(d_buy_qty, 1e-9)
            base_qty = d_sell_qty
        else:
            ratio = d_buy_qty / max(d_sell_qty, 1e-9)
            base_qty = d_buy_qty
        if ratio >= self.dominance_ratio * 2.5 and base_qty >= qty_thr * 2:
            return 4
        if ratio >= self.dominance_ratio * 1.5 and base_qty >= qty_thr:
            return 3
        if ratio >= self.dominance_ratio and base_qty >= qty_thr * 0.5:
            return 2
        return 2

    def _strong_gate(self, symbol: str, now_ms: int, t: str, d_sell_qty: float, d_buy_qty: float, d_sell: int, d_buy: int, intensity: int,
                      qty_thr: float, count_thr: int, intensity_thr: int, elapsed_ms: int,
                      tot_sell: int, tot_buy: int, tot_sell_qty: float, tot_buy_qty: float) -> bool:
        # 强门限说明：
        # - 先要求会话已运行至少 10s，避免瞬时尖峰
        # - spike：数量或次数需达到动态阈值的 3 倍
        # - intensity：强度需达到动态阈值的 3 倍
        # - dominance：比值需达到基础支配比的 2 倍，且数量达到动态阈值的 1.5 倍
        if elapsed_ms < self.strong_gate_min_session_ms:
            return False
        # 计算时间窗累计值
        window_ms = self.gate_window_ms
        sell_cnt_sum = 0
        buy_cnt_sum = 0
        sell_qty_sum = 0.0
        buy_qty_sum = 0.0
        dq = self._agg.get(symbol) or deque()
        while dq and now_ms - dq[0][0] > window_ms:
            dq.popleft()
        for ts, sc, bc, sq, bq in dq:
            sell_cnt_sum += sc
            buy_cnt_sum += bc
            sell_qty_sum += sq
            buy_qty_sum += bq
        # counts/qty 的窗口强门限（更稳定地识别持续单边）
        if t in ("force_spike_sell", "force_spike_buy"):
            base_qty = d_sell_qty if t.endswith("sell") else d_buy_qty
            base_cnt = d_sell if t.endswith("sell") else d_buy
            win_qty = sell_qty_sum if t.endswith("sell") else buy_qty_sum
            win_cnt = sell_cnt_sum if t.endswith("sell") else buy_cnt_sum
            # 同时引入“累计快照”直接判定：当3分钟累计总次数或总量达倍数阈值时也通过
            cum_cnt = tot_sell if t.endswith("sell") else tot_buy
            cum_qty = tot_sell_qty if t.endswith("sell") else tot_buy_qty
            return (
                (base_qty >= qty_thr * self.strong_gate_spike_mult or base_cnt >= count_thr * self.strong_gate_spike_mult)
                or (win_qty >= qty_thr * 3 or win_cnt >= count_thr * 6)
                or (cum_cnt >= count_thr * 6 or cum_qty >= qty_thr * 3)
                or (t.endswith("sell") and cum_cnt >= self.total_count_threshold_sell)
                or (t.endswith("buy") and cum_cnt >= self.total_count_threshold_buy)
            )
        if t == "force_intensity":
            return (
                intensity >= intensity_thr * self.strong_gate_intensity_mult
                or (sell_cnt_sum + buy_cnt_sum) >= intensity_thr * 6
                or (tot_sell + tot_buy) >= intensity_thr * 6
            )
        if t.endswith("sell_dominance"):
            ratio = d_sell_qty / max(d_buy_qty, 1e-9)
            base_qty = d_sell_qty
            win_ratio_qty = (sell_qty_sum / max(buy_qty_sum, 1e-9)) if (sell_qty_sum > 0 or buy_qty_sum > 0) else None
            win_ratio_cnt = sell_cnt_sum / max(buy_cnt_sum, 1)
        else:
            ratio = d_buy_qty / max(d_sell_qty, 1e-9)
            base_qty = d_buy_qty
            win_ratio_qty = (buy_qty_sum / max(sell_qty_sum, 1e-9)) if (sell_qty_sum > 0 or buy_qty_sum > 0) else None
            win_ratio_cnt = buy_cnt_sum / max(sell_cnt_sum, 1)
        # qty 支配或 counts 支配满足其一即可（counts 作为缺失 qty 的后备）
        qty_gate = ratio >= self.dominance_ratio * self.strong_gate_dominance_ratio_mult and base_qty >= qty_thr * self.strong_gate_dominance_qty_mult
        win_qty_gate = (win_ratio_qty is not None) and (win_ratio_qty >= self.dominance_ratio * self.strong_gate_dominance_ratio_mult) and ((sell_qty_sum if t.endswith("sell") else buy_qty_sum) >= qty_thr * 2)
        cnt_gate = win_ratio_cnt >= max(self.dominance_ratio, 3.0) and ((sell_cnt_sum if t.endswith("sell") else buy_cnt_sum) >= count_thr * 6)
        # 累计快照的支配后备：直接使用累计总量或累计次数比
        cum_ratio_qty = (tot_sell_qty / max(tot_buy_qty, 1e-9)) if t.endswith("sell") else (tot_buy_qty / max(tot_sell_qty, 1e-9))
        cum_ratio_cnt = (tot_sell / max(tot_buy, 1)) if t.endswith("sell") else (tot_buy / max(tot_sell, 1))
        cum_qty_gate = cum_ratio_qty >= self.dominance_ratio * self.strong_gate_dominance_ratio_mult and (tot_sell_qty if t.endswith("sell") else tot_buy_qty) >= qty_thr * 2
        cum_cnt_gate = cum_ratio_cnt >= max(self.dominance_ratio, 3.0) and (tot_sell if t.endswith("sell") else tot_buy) >= count_thr * 8
        if t == "force_rebound_buy":
            return True
        if t == "force_rebound_sell":
            return True
        return qty_gate or win_qty_gate or cnt_gate or cum_qty_gate or cum_cnt_gate

    def _budget_check(self, symbol: str, ts_ms: int, level: int) -> bool:
        # 分钟配额：窗口内事件数受限；重大事件（level>=5）不受限
        window_ms = self.emit_budget_window_s * 1000
        lst = self._symbol_budget.get(symbol) or []
        lst = [t for t in lst if ts_ms - t <= window_ms]
        self._symbol_budget[symbol] = lst
        if len(lst) >= self.emit_budget_max and level < 4:
            return False
        return True

    def _budget_record(self, symbol: str, ts_ms: int) -> None:
        # 记录一次事件时间戳，用于配额统计
        lst = self._symbol_budget.get(symbol) or []
        lst.append(ts_ms)
        self._symbol_budget[symbol] = lst

    async def run(self):
        self._running = True
        print("[ForceStatsConsumer] started, piping force_stats_stream:* -> raw_event_stream")
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
