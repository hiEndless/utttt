import pandas as pd
import ta


class RSI:
    def __init__(self, kline_data):
        self.kline_data = kline_data
        self.rsi_6 = 0.0
        self.rsi_12 = 0.0
        self.rsi_14 = 0.0
        self.rsi_24 = 0.0

    def calculate(self):
        closes = [float(item[4]) for item in self.kline_data]
        s = pd.Series(closes)
        self.rsi_6 = float(ta.momentum.rsi(s, window=6).iloc[-1]) if len(closes) >= 6 else 0.0
        self.rsi_12 = float(ta.momentum.rsi(s, window=12).iloc[-1]) if len(closes) >= 12 else 0.0
        self.rsi_14 = float(ta.momentum.rsi(s, window=14).iloc[-1]) if len(closes) >= 14 else 0.0
        self.rsi_24 = float(ta.momentum.rsi(s, window=24).iloc[-1]) if len(closes) >= 24 else 0.0
        return {"rsi6": self.rsi_6, "rsi12": self.rsi_12, "rsi14": self.rsi_14, "rsi24": self.rsi_24}
