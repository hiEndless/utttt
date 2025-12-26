import json
import redis
from event_center.config import cfg
from event_center.indicators_event_plugins import get_plugins
from event_center.indicators_event_plugins.meta_combo import load_weights, score_events, build_dashboard
import time
from event_center.raw_event import build_raw_event
import time
import json


def calculate_indicators(symbol: str, interval: str, db: int | None = None):
    client = redis.Redis(
        host=cfg.redis_host,
        port=cfg.redis_port,
        db=(db if db is not None else cfg.redis_db),
        password=(cfg.redis_password or None),
        decode_responses=True,
    )
    key = f"indicators:binance:{symbol}:{interval}"
    try:
        val = client.get(key)
        if not val:
            return {}
        return json.loads(val)
    except Exception:
        return {}


def read_klines(symbol: str, interval: str, db: int | None = None):
    client = redis.Redis(
        host=cfg.redis_host,
        port=cfg.redis_port,
        db=(db if db is not None else cfg.redis_db),
        password=(cfg.redis_password or None),
        decode_responses=True,
    )
    key = f"klines:binance:{symbol}:{interval}"
    try:
        val = client.get(key)
        if not val:
            return []
        return json.loads(val)
    except Exception:
        return []


# -----------------------------
# 事件生成器
# -----------------------------
class EventGenerator:
    def __init__(self, symbol: str, kline: list, interval: str):
        self.symbol = symbol
        self.ind = calculate_indicators(symbol, interval)
        self.events = []
        self.kline = kline
        self.interval = interval
        self.plugins = get_plugins()

    def generate_events(self):
        # print(f"[IndicatorsEventGenerator] started, piping indicators:{self.symbol}:{self.interval} -> {cfg.raw_stream}")
        self.events = []
        plugin_events = []
        for p in self.plugins:
            try:
                if hasattr(p, "supports") and not p.supports(self.symbol, self.interval, self.kline, self.ind):
                    req = getattr(p, "required_indicators", [])
                    missing = [k for k in (req or []) if k not in (self.ind or {})]
                    si = getattr(p, "supported_intervals", None)
                    print(f"[指标事件生成器] 跳过插件={getattr(p,'name',p.__class__.__name__)} 周期={self.interval} 缺少指标={missing} 支持周期={si}")
                    continue
                gen = p.generate(self.symbol, self.kline, self.ind, None, self.interval)
                plugin_events.extend(gen)
            except Exception:
                pass
        now_ms = int(time.time() * 1000)

        def _normalize_type(ev: dict) -> str:
            payload = ev.get("payload", {})
            signal = payload.get("signal") or ev.get("signal")
            side = payload.get("side") or ev.get("side")
            plugin = payload.get("plugin") or "unknown"
            interval = self.interval
            if signal in ("combo_bullish", "combo_bearish"):
                final_side = side or ("bullish" if "bull" in (signal or "") else "bearish")
                return f"combo.{interval}.{plugin}.{final_side}"
            if signal == "combo_neutral":
                return f"combo.{interval}.{plugin}.neutral"
            if signal:
                return f"combo.{interval}.{plugin}.{signal}"
            et = ev.get("type") or ev.get("event_type") or "unknown"
            return f"combo.{interval}.{plugin}.{et}"

        def _grade(payload: dict) -> int:
            try:
                strength = float(payload.get("strength", 0) or 0)
            except Exception:
                strength = 0.0
            if self.interval in ("1m",):
                strength -= 0.5
            try:
                side = str(payload.get("side") or "").lower()
                if side == "neutral":
                    strength -= 0.5
            except Exception:
                pass
            adx = payload.get("adx")
            vol_chg = payload.get("vol_chg")
            close = payload.get("close")
            atr = payload.get("atr")
            atr_ratio = None
            try:
                if close and atr is not None and float(close) > 0:
                    atr_ratio = float(atr) / float(close)
            except Exception:
                atr_ratio = None

            if strength >= 6 and (adx or 0) >= 25 and (vol_chg or 0) >= 1.8 and (atr_ratio or 0) >= 0.006:
                return 4
            if strength >= 5 and (adx or 0) >= 20 and (vol_chg or 0) >= 1.5 and (atr_ratio or 0) >= 0.004:
                return 3
            if strength >= 4 or (adx or 0) >= 18:
                return 2
            return 1
        for ev in plugin_events:
            try:
                payload = ev.get("payload") if isinstance(ev, dict) else {"raw": ev}
                etype = _normalize_type(ev if isinstance(ev, dict) else {"type": "unknown", "payload": payload})
                level = _grade(payload)
                ts_ms = int(ev.get("ts", now_ms)) if isinstance(ev, dict) else now_ms
                raw = build_raw_event(
                    exchange="binance",
                    symbol=self.symbol,
                    account_id="binance_public",
                    source="indicators_event_generator",
                    event_class="technical",
                    event_type=etype,
                    event_level=level,
                    timestamp_ms=ts_ms,
                    payload={**payload, "interval": self.interval},
                )
                self.events.append(raw)
            except Exception:
                pass
        try:
            weights = load_weights("event_center/event_plugins")
            scores = score_events(plugin_events, weights)
            dash = build_dashboard(scores)
            self.events.append(build_raw_event(exchange="binance", symbol=self.symbol, account_id="binance_public", source="indicators_event_generator", event_class="technical", event_type="meta_combo_score", event_level=1, timestamp_ms=now_ms, payload={"total": scores["total"], "per_plugin": scores["per_plugin"], "count": scores["count"]}))
            self.events.append(build_raw_event(exchange="binance", symbol=self.symbol, account_id="binance_public", source="indicators_event_generator", event_class="technical", event_type="meta_combo_dashboard", event_level=1, timestamp_ms=now_ms, payload=dash))
        except Exception:
            pass
        return self.events

    async def publish(self, writer):
        if not self.events:
            self.generate_events()
        await writer.write_many(self.events)


class RedisEventWriter:
    def __init__(self, redis):
        self.redis = redis
        # 设置事件信号出现的最小级别和窗口周期频率
        self.min_level_map = {"1m": 2, "5m": 2, "15m": 2, "30m": 2, "1h": 2, "2h": 2, "4h": 2, "1d": 2}
        self.dedup_window_ms = {"1m": 30000, "5m": 120000, "15m": 180000, "30m": 300000, "1h": 600000, "2h": 900000, "4h": 1800000, "1d": 3600000}
        self.emit_min_interval_ms = {"1m": 15000, "5m": 60000, "15m": 120000, "30m": 180000, "1h": 300000, "2h": 600000, "4h": 900000, "1d": 1800000}
        self.budget_window_s = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400, "1d": 86400}
        self.budget_max = {"1m": 3, "5m": 1, "15m": 2, "30m": 2, "1h": 2, "2h": 2, "4h": 2, "1d": 3}

    def _fp(self, payload: dict) -> str:
        try:
            def _round(v):
                if isinstance(v, float):
                    return round(v, 6)
                return v
            def _norm(x):
                if isinstance(x, dict):
                    return {k: _norm(x[k]) for k in sorted(x.keys())}
                if isinstance(x, list):
                    return [_norm(i) for i in x]
                return _round(x)
            return json.dumps(_norm(payload or {}), separators=(",", ":"), ensure_ascii=False)
        except Exception:
            return json.dumps(payload or {}, separators=(",", ":"), ensure_ascii=False)

    async def _should_emit(self, raw: dict) -> bool:
        try:
            symbol = raw.get("symbol")
            etype = raw.get("event_type")
            payload_s = raw.get("payload") or "{}"
            payload = json.loads(payload_s) if isinstance(payload_s, str) else payload_s
            interval = str(payload.get("interval") or "1m")
            level = 0
            try:
                level = int(raw.get("event_level", "0"))
            except Exception:
                level = 0
            now_ms = int(time.time() * 1000)

            min_lv = self.min_level_map.get(interval, 2)
            if level < min_lv:
                return False

            fp = self._fp(payload)
            key_base = f"ind_ev_gate:{symbol}:{interval}:{etype}"
            last_ts_s = await self.redis.get(key_base + ":last_ts")
            last_fp = await self.redis.get(key_base + ":last_fp")
            last_ts = int(last_ts_s) if last_ts_s else 0
            if now_ms - last_ts < self.emit_min_interval_ms.get(interval, 60000):
                if last_fp == fp and now_ms - last_ts < self.dedup_window_ms.get(interval, 60000):
                    return False

            # budget check
            bw = self.budget_window_s.get(interval, 120)
            bkey = key_base + ":budget"
            try:
                cur = await self.redis.get(bkey)
                cur_n = int(cur) if cur else 0
            except Exception:
                cur_n = 0
            if cur_n >= self.budget_max.get(interval, 1) and level < 4:
                return False
            # record state
            try:
                await self.redis.set(key_base + ":last_ts", str(now_ms))
                await self.redis.set(key_base + ":last_fp", fp)
                # bump budget with TTL window
                pipe = self.redis.pipeline()
                await pipe.incr(bkey)
                await pipe.expire(bkey, bw)
                await pipe.execute()
            except Exception:
                pass
            return True
        except Exception:
            return True

    async def write_many(self, events):
        for raw in events:
            try:
                ok = await self._should_emit(raw)
                if not ok:
                    continue
                await self.redis.xadd(cfg.raw_stream, raw)
            except Exception:
                pass


# -----------------------------
# 使用示例
# -----------------------------
if __name__ == "__main__":
    res = calculate_indicators('BTCUSDT', '1m')
    print(res)
