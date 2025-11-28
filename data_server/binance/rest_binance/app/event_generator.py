from signals import EMA, MA, MACD, RSI, KDJ, BollingerBandSignal, VolatilitySignal, SupportResistance
from event_plugins import get_plugins
from event_plugins.meta_combo import load_weights, score_events, build_dashboard
from event_plugins.base import build_event


def calculate_indicators(klines_data):
    return {
        "boll": BollingerBandSignal(klines_data).calculate(),
        "ema": EMA(klines_data).calculate(),
        "ma": MA(klines_data).calculate(),
        "rsi": RSI(klines_data).calculate(),
        "macd": MACD(klines_data).calculate(),
        "kdj": KDJ(klines_data).calculate(),
        "sr": SupportResistance(klines_data).calculate(),
        "vol": VolatilitySignal(klines_data).calculate(),
    }


# -----------------------------
# 事件生成器
# -----------------------------
class EventGenerator:
    def __init__(self, symbol: str, kline: list, interval: str):
        self.symbol = symbol
        self.ind = calculate_indicators(kline)
        self.events = []
        self.kline = kline
        self.interval = interval
        self.plugins = get_plugins()

    def generate_events(self):
        self.events = []
        prev_ind = None
        if len(self.kline) > 1:
            try:
                prev_ind = calculate_indicators(self.kline[:-1])
            except Exception:
                prev_ind = None
        for p in self.plugins:
            try:
                if hasattr(p, "supports") and not p.supports(self.symbol, self.interval, self.kline, self.ind):
                    continue
                self.events.extend(p.generate(self.symbol, self.kline, self.ind, prev_ind, self.interval))
            except Exception:
                pass
        try:
            weights = load_weights("data_server/binance/rest_binance/app/event_plugins")
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
    pass
