import json
from signals import EMA, MA, MACD, RSI, KDJ, BollingerBandSignal, VolatilitySignal, SupportResistance

try:
    from .redis_client import get_redis_client
except ImportError:
    from redis_client import get_redis_client


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
# 指标生成器（写入 Redis）
# -----------------------------
class EventGenerator:
    def __init__(self, symbol: str, kline: list, interval: str):
        self.symbol = symbol
        self.ind = calculate_indicators(kline)
        self.events = []
        self.kline = kline
        self.interval = interval

    async def publish(self, db: int | None = None):
        client = get_redis_client(db)
        indicators_key = f"indicators:binance:{self.symbol}:{self.interval}"
        klines_key = f"klines:binance:{self.symbol}:{self.interval}"
        await client.set(indicators_key, json.dumps(self.ind, ensure_ascii=False))
        await client.set(klines_key, json.dumps(self.kline, ensure_ascii=False))
        try:
            if isinstance(self.kline, list) and len(self.kline) >= 2:
                prev_ind = calculate_indicators(self.kline[:-1])
                prev_key = f"indicators:prev:binance:{self.symbol}:{self.interval}"
                await client.set(prev_key, json.dumps(prev_ind, ensure_ascii=False))
        except Exception:
            pass
        return True


# -----------------------------
# 使用示例
# -----------------------------
if __name__ == "__main__":
    pass
