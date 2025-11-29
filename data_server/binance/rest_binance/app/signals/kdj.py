class KDJ:
    def __init__(self, kline_data):
        self.kline_data = kline_data  # [[1747815300000, '106700.30', '106700.30', '106304.10', '106415.90', '2821.384', 1747816199999, '300240460.76000', 46744, '1126.331', '119847154.76890', '0'], [1747816200000, '106416.00', '106499.10', '106322.20', '106361.70', '1313.441', 1747817099999, '139759489.65290', 29581, '590.449', '62827650.87300', '0']]
        self.k = 0
        self.d = 0
        self.j = 0

    def calculate(self, period=9, k_smooth=3, d_smooth=3):
        """
        计算KDJ指标（K、D、J）
        period: 计算RSV的周期，默认9
        k_smooth: K值平滑周期，默认3
        d_smooth: D值平滑周期，默认3
        """
        if len(self.kline_data) < period:
            raise ValueError("K线数据不足以计算KDJ")
        close_prices = [float(item[4]) for item in self.kline_data]
        high_prices = [float(item[2]) for item in self.kline_data]
        low_prices = [float(item[3]) for item in self.kline_data]
        rsv_list = []
        for i in range(period - 1, len(close_prices)):
            low = min(low_prices[i - period + 1:i + 1])
            high = max(high_prices[i - period + 1:i + 1])
            close = close_prices[i]
            rsv = 0 if high == low else (close - low) / (high - low) * 100
            rsv_list.append(rsv)
        k = 50
        d = 50
        k_list = []
        d_list = []
        for rsv in rsv_list:
            k = k * (k_smooth - 1) / k_smooth + rsv / k_smooth
            d = d * (d_smooth - 1) / d_smooth + k / d_smooth
            k_list.append(k)
            d_list.append(d)
        j = 3 * k_list[-1] - 2 * d_list[-1]
        self.k = k_list[-1]
        self.d = d_list[-1]
        self.j = j
        return {
            "k": self.k,
            "d": self.d,
            "j": self.j
        }