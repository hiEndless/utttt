import asyncio
import json
import time
from typing import Dict, List, Tuple

from redis import asyncio as aioredis

from event_center.config import cfg
from event_center.pipeline.raw_event import build_raw_event


def normalize_alert_type(atype: str) -> str:
    m = {
        "pct_change_up": "price.pct_up",
        "pct_change_down": "price.pct_down",
        "zscore_spike": "price.spike",
        "bid_collapse": "depth.bid_collapse",
        "ask_collapse": "depth.ask_collapse",
        "liquidity_collapse": "depth.liquidity_collapse",
        "one_side_up": "trend.one_side_up",
        "one_side_down": "trend.one_side_down",
    }
    return m.get(atype, atype)


def grade_alert(atype: str, details: dict) -> int:
    try:
        if atype in ("pct_change_up", "pct_change_down"):
            pct = abs(float(details.get("pct", 0.0)))
            if pct >= 0.05:
                return 4
            if pct >= 0.02:
                return 3
            if pct >= 0.01:
                return 2
            return 1
        if atype == "zscore_spike":
            z = abs(float(details.get("z", 0.0)))
            if z >= 12:
                return 4
            if z >= 8:
                return 3
            if z >= 5:
                return 2
            return 1
        if atype in ("bid_collapse", "ask_collapse"):
            ratio = float(details.get("ratio", 1.0))
            streak = int(details.get("streak", 1))
            if ratio <= 0.10 and streak >= 3:
                return 4
            if ratio <= 0.20 and streak >= 2:
                return 3
            if ratio <= 0.30:
                return 2
            return 1
        if atype == "liquidity_collapse":
            ratios = details.get("ratio", []) or []
            try:
                min_ratio = min([float(r) for r in ratios]) if ratios else 1.0
            except Exception:
                min_ratio = 1.0
            count = int(details.get("count", 1))
            if count >= 2 and min_ratio <= 0.15:
                return 4
            if min_ratio <= 0.25:
                return 3
            return 2
        if atype in ("one_side_up", "one_side_down"):
            pct = abs(float(details.get("pct", 0.0)))
            count = int(details.get("count", 1))
            if count >= 10 and pct >= 0.05:
                return 4
            if count >= 5 and pct >= 0.03:
                return 3
            if count >= 3 and pct >= 0.01:
                return 2
            return 1
    except Exception:
        return 1
    return 1


class AlertsConsumer:
    def __init__(self, redis_url: str = cfg.redis_url, scan_interval_s: float = 5.0, exchange: str = "binance"):
        self.redis = aioredis.from_url(redis_url)
        self.scan_interval_s = scan_interval_s
        self.exchange = exchange
        self.stream_offsets: Dict[str, str] = {}
        self._running = False
        self.dedup_window_ms = 2000  # 去重窗口：同指纹事件在该窗口内不重复
        self.emit_min_interval_ms = 1000  # 最小生成间隔：同类型至少间隔指定毫秒
        self._last_emit_ts: Dict[Tuple[str, str], int] = {}
        self._last_payload_fp: Dict[Tuple[str, str], str] = {}
        self.emit_budget_window_s = 60  # 配额窗口（秒）：统计每个 symbol 的事件数量
        self.emit_budget_max = 1  # 配额上限：窗口内最多允许 level<5 的事件数量
        self._symbol_budget: Dict[str, List[int]] = {}  # 每个 symbol 已发事件的时间戳列表

    async def _discover_streams(self):
        try:
            cursor = 0
            keys: List[str] = []
            pattern = f"alerts:{self.exchange}:*"
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

    async def _to_raw_event(self, symbol: str, alert_type: str, ts_ms: int, details: dict, level: int) -> Dict[str, str]:
        dir_map = {
            "price.pct_up": "bullish",
            "price.pct_down": "bearish",
            "trend.one_side_up": "bullish",
            "trend.one_side_down": "bearish",
            "depth.ask_collapse": "bullish",
            "depth.bid_collapse": "bearish",
        }
        direction = dir_map.get(alert_type, "neutral")
        strength = float(level)
        try:
            if "pct" in details:
                strength = abs(float(details.get("pct", 0.0))) * 100.0
            elif "z" in details:
                strength = abs(float(details.get("z", 0.0))) / 4.0
            elif "ratio" in details:
                r = float(details.get("ratio", 1.0))
                strength = max(1.0, 0.3 / max(r, 1e-9))
            elif "count" in details:
                c = float(details.get("count", 0.0))
                strength = max(1.0, c / 3.0)
        except Exception:
            pass
        payload = {
            "summary": {
                "direction": direction,
                "signal_strength": strength,
                "primary_tf": "1m",
            },
            "evidence": {
                "plugins": [{"name": alert_type, "tfs": ["1m"]}],
            },
            "details": details,
        }
        return build_raw_event(
            exchange=self.exchange,
            symbol=symbol,
            account_id=f"{self.exchange}_public",
            source="alerts_consumer",
            event_class="market",
            event_type=alert_type,
            event_level=level,
            timestamp_ms=ts_ms,
            payload=payload,
        )

    def _normalize_alert_type(self, atype: str) -> str:
        return normalize_alert_type(atype)

    def _grade(self, atype: str, details: dict) -> int:
        return grade_alert(atype, details)

    def _fingerprint(self, details: dict) -> str:
        # 生成稳定的 payload 指纹：对浮点数做四舍五入、对字典按键排序、列表递归归一化
        # 用于在短时间内判定“相同事件”并进行去重
        try:
            def _round(v):
                if isinstance(v, float):
                    return round(v, 6)
                return v
            def _normalize(x):
                if isinstance(x, dict):
                    return {k: _normalize(x[k]) for k in sorted(x.keys())}
                if isinstance(x, list):
                    return [_normalize(i) for i in x]
                return _round(x)
            norm = _normalize(details)
            return json.dumps(norm, separators=(",", ":"), ensure_ascii=False)
        except Exception:
            return json.dumps(details, separators=(",", ":"), ensure_ascii=False)

    def _should_emit(self, symbol: str, norm_type: str, ts_ms: int, details: dict) -> bool:
        # 限频 + 指纹去重：
        # 若距离上次同类型事件不足最小间隔，则仅当指纹发生变化才允许；
        # 若指纹未变且处于去重窗口内，则丢弃该事件。
        key = (symbol, norm_type)
        last_ts = self._last_emit_ts.get(key, 0)
        if ts_ms - last_ts < self.emit_min_interval_ms:
            fp = self._fingerprint(details)
            last_fp = self._last_payload_fp.get(key)
            if last_fp == fp and ts_ms - last_ts < self.dedup_window_ms:
                return False
        return True

    def _passes_gating(self, norm_type: str, level: int, details: dict) -> bool:
        # 强门限：严格筛选趋势/流动性类事件，压制震荡期噪声；
        # 其它类型仅允许高等级（level>=4）通过。
        if norm_type in ("trend.one_side_up", "trend.one_side_down"):
            try:
                count = int(details.get("count", 0))
                pct = abs(float(details.get("pct", 0.0)))
            except Exception:
                count, pct = 0, 0.0
            return count >= 8 and pct >= 0.03
        if norm_type == "depth.liquidity_collapse":
            ratios = details.get("ratio", []) or []
            try:
                min_ratio = min([float(r) for r in ratios]) if ratios else 1.0
            except Exception:
                min_ratio = 1.0
            count = int(details.get("count", 0) or 0)
            return count >= 2 and min_ratio <= 0.15
        return level >= 4

    def _budget_check(self, symbol: str, ts_ms: int, level: int) -> bool:
        # 分钟配额：每个 symbol 在窗口内仅允许有限事件；
        # 重大事件（level>=5）不受配额限制。
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
                        norm_type = self._normalize_alert_type(alert_type)
                        level = self._grade(alert_type, details)
                        # 依次应用：限频/去重 -> 强门限 -> 分钟配额
                        if not self._should_emit(symbol, norm_type, ts_ms, details):
                            continue
                        if not self._passes_gating(norm_type, level, details):
                            continue
                        if not self._budget_check(symbol, ts_ms, level):
                            continue
                        raw = await self._to_raw_event(symbol, norm_type, ts_ms, details, level)
                        await self.redis.xadd(cfg.raw_stream, raw)
                        self._last_emit_ts[(symbol, norm_type)] = ts_ms
                        self._last_payload_fp[(symbol, norm_type)] = self._fingerprint(details)
                        self._budget_record(symbol, ts_ms)
                        print(f"[AlertsConsumer] -> event_id={raw['event_id']} symbol={symbol} type={norm_type} level={level}")
                    except Exception as e:
                        print(f"[AlertsConsumer] error stream={stream_name} entry={entry_id} err={e}")


if __name__ == "__main__":
    ac = AlertsConsumer()
    try:
        asyncio.run(ac.run())
    except KeyboardInterrupt:
        pass
