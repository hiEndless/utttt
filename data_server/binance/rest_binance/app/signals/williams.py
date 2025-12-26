import pandas as pd
import ta


class WilliamsR:
    def __init__(self, kline_data):
        self.kline_data = kline_data
        self.value = 0.0

    def calculate(self, period=14):
        high = pd.Series([float(x[2]) for x in self.kline_data])
        low = pd.Series([float(x[3]) for x in self.kline_data])
        close = pd.Series([float(x[4]) for x in self.kline_data])
        if len(close) < period:
            self.value = 0.0
            return {"williams_r": self.value}
        wr = ta.momentum.williams_r(high, low, close, lbp=period)
        self.value = float(wr.iloc[-1])
        return {"williams_r": self.value}
