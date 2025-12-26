import pandas as pd
import ta


class MACD:
    def __init__(self, kline_data):
        self.kline_data = kline_data
        self.dif = 0.0
        self.dea = 0.0
        self.macd = 0.0

    def calculate(self, short_period=12, long_period=26, signal_period=9):
        closes = [float(item[4]) for item in self.kline_data]
        if len(closes) < max(long_period, short_period) + signal_period:
            raise ValueError("K线数据不足以计算MACD")
        s = pd.Series(closes)
        dif = ta.trend.macd(s, window_slow=long_period, window_fast=short_period)
        dea = ta.trend.macd_signal(s, window_slow=long_period, window_fast=short_period, window_sign=signal_period)
        hist = ta.trend.macd_diff(s, window_slow=long_period, window_fast=short_period, window_sign=signal_period)
        self.dif = float(dif.iloc[-1])
        self.dea = float(dea.iloc[-1])
        self.macd = float(hist.iloc[-1]) * 2.0
        return {"dif": self.dif, "dea": self.dea, "macd": self.macd}
