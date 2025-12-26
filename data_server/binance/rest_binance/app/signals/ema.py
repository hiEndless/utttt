import pandas as pd
import ta


class EMA:
    def __init__(self, kline_data):
        self.kline_data = kline_data
        self.ema_5 = None
        self.ema_7 = None
        self.ema_12 = None
        self.ema_20 = None
        self.ema_26 = None
        self.ema_50 = None
        self.ema_100 = None
        self.ema_200 = None

    def calculate(self):
        closes = [float(item[4]) for item in self.kline_data]
        s = pd.Series(closes)
        self.ema_5 = float(ta.trend.ema_indicator(s, window=5).iloc[-1]) if len(closes) >= 5 else None
        self.ema_7 = float(ta.trend.ema_indicator(s, window=7).iloc[-1]) if len(closes) >= 7 else None
        self.ema_12 = float(ta.trend.ema_indicator(s, window=12).iloc[-1]) if len(closes) >= 12 else None
        self.ema_20 = float(ta.trend.ema_indicator(s, window=20).iloc[-1]) if len(closes) >= 20 else None
        self.ema_26 = float(ta.trend.ema_indicator(s, window=26).iloc[-1]) if len(closes) >= 26 else None
        self.ema_50 = float(ta.trend.ema_indicator(s, window=50).iloc[-1]) if len(closes) >= 50 else None
        self.ema_100 = float(ta.trend.ema_indicator(s, window=100).iloc[-1]) if len(closes) >= 100 else None
        self.ema_200 = float(ta.trend.ema_indicator(s, window=200).iloc[-1]) if len(closes) >= 200 else None
        return {"ema5": self.ema_5, "ema7": self.ema_7, "ema12": self.ema_12, "ema20": self.ema_20,
                "ema26": self.ema_26, "ema50": self.ema_50, "ema100": self.ema_100, "ema200": self.ema_200}
