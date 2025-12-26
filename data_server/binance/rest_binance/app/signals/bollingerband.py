import pandas as pd
import ta


class BollingerBandSignal:
    def __init__(self, kline_data):
        self.kline_data = kline_data
        self.upper_band = 0.0
        self.lower_band = 0.0
        self.middle_band = 0.0
        self.bandwidth = 0.0
        self.percent_b = 0.0

    def calculate(self, period=20, num_std=2):
        closes = [float(item[4]) for item in self.kline_data]
        if len(closes) < period:
            raise ValueError("K线数据不足以计算布林带")
        s = pd.Series(closes)
        bb = ta.volatility.BollingerBands(close=s, window=period, window_dev=num_std)
        self.upper_band = float(bb.bollinger_hband().iloc[-1])
        self.middle_band = float(bb.bollinger_mavg().iloc[-1])
        self.lower_band = float(bb.bollinger_lband().iloc[-1])
        self.bandwidth = float(bb.bollinger_wband().iloc[-1])
        self.percent_b = float(bb.bollinger_pband().iloc[-1])
        return {"upper_band": self.upper_band, "middle_band": self.middle_band, "lower_band": self.lower_band,
                "bandwidth": self.bandwidth, "percent_b": self.percent_b}
