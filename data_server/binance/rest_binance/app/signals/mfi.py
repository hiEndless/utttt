import pandas as pd
import ta


class MFI:
    def __init__(self, kline_data):
        self.kline_data = kline_data
        self.value = 0.0

    def calculate(self, window=14):
        high = pd.Series([float(x[2]) for x in self.kline_data])
        low = pd.Series([float(x[3]) for x in self.kline_data])
        close = pd.Series([float(x[4]) for x in self.kline_data])
        volume = pd.Series([float(x[5]) for x in self.kline_data])
        if len(close) < window:
            self.value = 0.0
            return {"mfi": self.value}
        mfi = ta.volume.money_flow_index(high, low, close, volume, window=window)
        self.value = float(mfi.iloc[-1])
        return {"mfi": self.value}
