import json
import redis
from event_center.config import cfg
from event_center.indicators_event_plugins import get_plugins
from event_center.indicators_event_plugins.meta_combo import load_weights, score_events, build_dashboard
import time
from event_center.raw_event import build_raw_event


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
        self.events = []
        plugin_events = []
        for p in self.plugins:
            try:
                if hasattr(p, "supports") and not p.supports(self.symbol, self.interval, self.kline, self.ind):
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
            if signal in ("combo_bullish", "combo_bearish"):
                return f"tech.combo.{side or ('bullish' if 'bull' in (signal or '') else 'bearish')}"
            if signal:
                return f"tech.signal.{signal}"
            et = ev.get("type") or ev.get("event_type")
            return f"tech.signal.{et or 'unknown'}"

        def _grade(payload: dict) -> int:
            try:
                strength = float(payload.get("strength", 0) or 0)
            except Exception:
                strength = 0.0
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
                return 5
            if strength >= 5 and (adx or 0) >= 20 and (vol_chg or 0) >= 1.5 and (atr_ratio or 0) >= 0.004:
                return 4
            if strength >= 4 or (adx or 0) >= 18:
                return 3
            return 2
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
                    payload=payload,
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


# -----------------------------
# 使用示例
# -----------------------------
if __name__ == "__main__":
    res = calculate_indicators('BTCUSDT', '1m')
    print(res)

