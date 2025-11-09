

class BollingerBandSignal:
    def __init__(self, kline_data):
        self.kline_data = kline_data  # [[1747815300000, '106700.30', '106700.30', '106304.10', '106415.90', '2821.384', 1747816199999, '300240460.76000', 46744, '1126.331', '119847154.76890', '0'], [1747816200000, '106416.00', '106499.10', '106322.20', '106361.70', '1313.441', 1747817099999, '139759489.65290', 29581, '590.449', '62827650.87300', '0']]
        self.close_prices = []
        self.upper_band = 0  # 布林带上轨
        self.lower_band = 0  # 布林带下轨
        self.middle_band = 0  # 布林带中轨
        self.bandwidth = 0  # 布林带带宽
        self.percent_b = 0  # 百分比

    def calculate(self, period=20, num_std=2):
        """
        计算布林带指标。
        period: 均线周期，默认20
        num_std: 标准差倍数，默认2
        """
        self.close_prices = [float(item[4]) for item in self.kline_data]  # 收盘价
        if len(self.close_prices) < period:
            raise ValueError("K线数据不足以计算布林带")
        # 只计算最后一根K线的布林带
        window = self.close_prices[-period:]
        mean = sum(window) / period
        std = (sum([(x - mean) ** 2 for x in window]) / period) ** 0.5
        self.middle_band = mean
        self.upper_band = mean + num_std * std
        self.lower_band = mean - num_std * std
        self.bandwidth = (self.upper_band - self.lower_band) / self.middle_band if self.middle_band != 0 else 0
        last_close = self.close_prices[-1]
        self.percent_b = (last_close - self.lower_band) / (self.upper_band - self.lower_band) if (self.upper_band - self.lower_band) != 0 else 0
        return {
            "upper_band": round(self.upper_band, 2),
            "middle_band": round(self.middle_band, 2),
            "lower_band": round(self.lower_band, 2),
            "bandwidth": round(self.bandwidth, 6),
            "percent_b": round(self.percent_b, 6)
        }

