import asyncio
import json
import time
from redis import asyncio as aioredis

from event_center.config import cfg
import os
import yaml


class L1Aggregator:
    def __init__(self, redis_url: str = cfg.redis_url):
        self.redis = aioredis.from_url(redis_url)
        self.neutral_band = 2.0
        self.short_boost = 0.2
        self.mid_boost = 0.3
        self.window_seconds = 300
        self.window_count = 10
        self.class_map = self._load_class_map()

    def _load_class_map(self):
        try:
            base_dir = os.path.dirname(__file__)
            cfg_dir = os.path.join(base_dir, "indicators_event", "config")
            with open(os.path.join(cfg_dir, "indicator_class_map.yaml"), "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _infer_cls(self, plugin_name: str):
        m = self.class_map or {}
        by_plug = (m.get("by_plugin") or {})
        for cls, names in by_plug.items():
            if isinstance(names, list) and str(plugin_name or "").lower() in [n.lower() for n in names]:
                return cls
        # fallback by keyword
        n = str(plugin_name or "").lower()
        for kw, cls in [
            ("macd", "trend"),
            ("ema", "trend"),
            ("ma", "trend"),
            ("boll", "volatility"),
            ("williams", "momentum"),
            ("rsi", "momentum"),
            ("kdj", "momentum"),
            ("atr", "volatility"),
        ]:
            if kw in n:
                return cls
        return "unknown"

    async def _update_and_fetch_window(self, symbol: str, item: dict):
        key = f"l1:win:{symbol}"
        ts = int(item.get("ts") or int(time.time()))
        member = json.dumps(item, ensure_ascii=False)
        try:
            await self.redis.zadd(key, {member: ts})
        except Exception:
            pass
        cutoff = ts - self.window_seconds
        try:
            await self.redis.zremrangebyscore(key, 0, cutoff)
        except Exception:
            pass
        try:
            entries = await self.redis.zrevrange(key, 0, self.window_count - 1, withscores=False)
        except Exception:
            entries = []
        out = []
        for e in entries:
            try:
                obj = json.loads(e)
                if int(obj.get("ts") or 0) >= cutoff:
                    out.append(obj)
            except Exception:
                continue
        out.sort(key=lambda x: int(x.get("ts") or 0))
        return out

    def _aggregate_structure(self, items: list):
        if not items:
            return {"direction": "neutral", "total_score": 0.0, "market_state": "range", "short_term_bias": False, "mid_term_bias": False}
        has_trend = any((i.get("cls") == "trend" and i.get("dir") in ("bullish", "bearish") and float(i.get("score") or 0.0) >= 0.0) for i in items)
        total = 0.0
        short_bias = False
        mid_bias = False
        for i in items:
            sc = float(i.get("score") or 0.0)
            d = i.get("dir")
            w = 1.0
            if i.get("cls") != "trend" and has_trend:
                w *= 0.5
            align = i.get("align") or {}
            bulls = align.get("bullish") or []
            bears = align.get("bearish") or []
            def has_pair(lst, a, b):
                return (a in lst) and (b in lst)
            if has_pair(bulls + bears, "1m", "5m"):
                w *= (1.0 + self.short_boost)
                short_bias = True
            if has_pair(bulls + bears, "15m", "1h"):
                w *= (1.0 + self.mid_boost)
                mid_bias = True
            signed = sc if d == "bullish" else (-sc if d == "bearish" else 0.0)
            total += signed * w
        direction = "neutral" if abs(total) < self.neutral_band else ("bullish" if total > 0 else "bearish")
        state = "trend" if has_trend and direction != "neutral" else ("range" if direction == "neutral" else "momentum")
        return {"direction": direction, "total_score": total, "market_state": state, "short_term_bias": short_bias, "mid_term_bias": mid_bias}

    async def process_l0_event(self, entry_id, data):
        event = data
        symbol = event.get("symbol")
        etype = event.get("type") or event.get("event_type") or ""
        payload = event.get("payload") or {}
        raw = payload.get("raw") or {}
        l0 = payload.get("l0") or {}
        direction = str(l0.get("l0_direction") or raw.get("direction") or "").lower()
        score = float(l0.get("l0_score") or raw.get("signal_strength") or 0.0)
        align = raw.get("timeframe_alignment") or {}
        cls = self._infer_cls(etype)
        now = int(time.time())
        win_item = {"ts": now, "plugin": etype, "cls": cls, "dir": direction, "score": score, "align": align}
        items = await self._update_and_fetch_window(symbol, win_item)
        agg = self._aggregate_structure(items)
        pr = "high" if agg["market_state"] == "trend" else ("medium" if agg["market_state"] == "range" else "low")
        l1 = {
            "account_id": event.get("account_id"),
            "symbol": symbol,
            "stage": "l1",
            "timestamp": now,
            "direction": agg["direction"],
            "total_score": agg["total_score"],
            "market_state": agg["market_state"],
            "short_term_bias": str(agg["short_term_bias"]).lower(),
            "mid_term_bias": str(agg["mid_term_bias"]).lower(),
            "result_priority": pr,
        }
        l1 = {k: ("" if v is None else v) for k, v in l1.items()}
        await self.redis.xadd(cfg.l1_stream, l1)
        print(f"[L1] 输出 symbol={symbol} 状态={agg['market_state']} 方向={agg['direction']} 分数={agg['total_score']} 优先级={pr}")

    async def run(self):
        group = "l1_group"
        consumer = "l1_consumer_1"
        try:
            await self.redis.xgroup_create(cfg.l0_stream, group, id="0", mkstream=True)
        except Exception:
            pass
        print(f"[L1] 启动 输入流={cfg.l0_stream} 输出流={cfg.l1_stream} 消费组={group}")
        while True:
            res = await self.redis.xreadgroup(group, consumer, streams={cfg.l0_stream: ">"}, count=20, block=5000)
            if not res:
                continue
            for stream_name, entries in res:
                for entry_id, fields in entries:
                    ev = {k.decode(): v.decode() for k, v in fields.items()}
                    if "payload" in ev:
                        try:
                            ev["payload"] = json.loads(ev["payload"])
                        except Exception:
                            ev["payload"] = {}
                    try:
                        print(f"[L1] 读入 entry_id={entry_id.decode()} 类型={ev.get('type')} 账户={ev.get('account_id')}")
                        await self.process_l0_event(entry_id.decode(), ev)
                        await self.redis.xack(cfg.l0_stream, group, entry_id)
                        print(f"[L1] 确认 entry_id={entry_id.decode()}")
                    except Exception as e:
                        print(f"[L1] 错误 entry_id={entry_id.decode()} 错误={e}")


if __name__ == "__main__":
    la = L1Aggregator()
    asyncio.run(la.run())
