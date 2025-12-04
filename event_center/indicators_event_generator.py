import json
import redis
from event_center.config import cfg
from indicators_event_plugins import get_plugins
from indicators_event_plugins.meta_combo import load_weights, score_events, build_dashboard
from indicators_event_plugins.base import build_event


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
        prev_ind = None
        for p in self.plugins:
            try:
                if hasattr(p, "supports") and not p.supports(self.symbol, self.interval, self.kline, self.ind):
                    continue
                self.events.extend(p.generate(self.symbol, self.kline, self.ind, prev_ind, self.interval))
            except Exception:
                pass
        try:
            weights = load_weights("event_center/event_plugins")
            scores = score_events(self.events, weights)
            dash = build_dashboard(scores)
            self.events.append(build_event(self.symbol, self.kline, "meta_combo_score", {"total": scores["total"], "per_plugin": scores["per_plugin"], "count": scores["count"]}, self.interval))
            self.events.append(build_event(self.symbol, self.kline, "meta_combo_dashboard", dash, self.interval))
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

