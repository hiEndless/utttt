import pandas as pd
import ta


class MA:
    def __init__(self, kline_data):
        self.kline_data = kline_data
        self.ma_5 = 0.0
        self.ma_10 = 0.0
        self.ma_20 = 0.0
        self.ma_50 = 0.0
        self.ma_200 = 0.0

    def calculate(self):
        closes = [float(item[4]) for item in self.kline_data]
        s = pd.Series(closes)

        def sma_or_zero(window):
            if len(closes) < window:
                return 0.0
            return float(ta.trend.sma_indicator(s, window=window).iloc[-1])

        self.ma_5 = sma_or_zero(5)
        self.ma_10 = sma_or_zero(10)
        self.ma_20 = sma_or_zero(20)
        self.ma_50 = sma_or_zero(50)
        self.ma_200 = sma_or_zero(200)
        return {"ma5": self.ma_5, "ma10": self.ma_10, "ma20": self.ma_20, "ma50": self.ma_50, "ma200": self.ma_200}
