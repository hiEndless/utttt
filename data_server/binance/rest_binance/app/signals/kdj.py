import pandas as pd
import ta


class KDJ:
    def __init__(self, kline_data):
        self.kline_data = kline_data
        self.k = 0.0
        self.d = 0.0
        self.j = 0.0

    def calculate(self, period=9, k_smooth=3, d_smooth=3):
        if len(self.kline_data) < period:
            raise ValueError("K线数据不足以计算KDJ")
        high = pd.Series([float(item[2]) for item in self.kline_data])
        low = pd.Series([float(item[3]) for item in self.kline_data])
        close = pd.Series([float(item[4]) for item in self.kline_data])
        k = ta.momentum.stoch(high, low, close, window=period, smooth_window=k_smooth)
        d = ta.momentum.stoch_signal(high, low, close, window=period, smooth_window=d_smooth)
        self.k = float(k.iloc[-1])
        self.d = float(d.iloc[-1])
        self.j = 3 * self.k - 2 * self.d
        return {"k": self.k, "d": self.d, "j": self.j}
