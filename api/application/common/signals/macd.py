class MACD:
    def __init__(self, kline_data):
        self.kline_data = kline_data  # [[1747815300000, '106700.30', '106700.30', '106304.10', '106415.90', '2821.384', 1747816199999, '300240460.76000', 46744, '1126.331', '119847154.76890', '0'], [1747816200000, '106416.00', '106499.10', '106322.20', '106361.70', '1313.441', 1747817099999, '139759489.65290', 29581, '590.449', '62827650.87300', '0']]
        self.dif = 0
        self.dea = 0
        self.macd = 0

    def calculate(self, short_period=12, long_period=26, signal_period=9):
        """
        计算MACD指标（DIF, DEA, MACD）
        short_period: 短期EMA周期，默认12
        long_period: 长期EMA周期，默认26
        signal_period: DEA（信号线）周期，默认9
        """
        close_prices = [float(item[4]) for item in self.kline_data]
        if len(close_prices) < long_period + signal_period:
            raise ValueError("K线数据不足以计算MACD")
        def ema(prices, period):
            ema_values = []
            multiplier = 2 / (period + 1)
            for i, price in enumerate(prices):
                if i == 0:
                    ema_values.append(price)
                else:
                    ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
            return ema_values
        ema_short = ema(close_prices, short_period)
        ema_long = ema(close_prices, long_period)
        dif_list = [s - l for s, l in zip(ema_short, ema_long)]
        dea_list = ema(dif_list, signal_period)
        macd_list = [(d - dea) * 2 for d, dea in zip(dif_list, dea_list)]
        self.dif = dif_list[-1]
        self.dea = dea_list[-1]
        self.macd = macd_list[-1]
        return {
            "dif": round(self.dif, 4),
            "dea": round(self.dea, 4),
            "macd": round(self.macd, 4)
        }