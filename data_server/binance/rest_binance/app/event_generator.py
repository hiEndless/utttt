from signals import EMA, MA, MACD, RSI, KDJ, BollingerBandSignal, VolatilitySignal, SupportResistance
from event_plugins import get_plugins
import time


def _last_ts(kline):
    try:
        return int(kline[-1][6])
    except Exception:
        try:
            return int(kline[-1][0])
        except Exception:
            return int(time.time())


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
                self.events.extend(p.generate(self.symbol, self.kline, self.ind, prev_ind, self.interval))
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
