class RSI:
    def __init__(self, kline_data):
        self.kline_data = kline_data  # [[1747815300000, '106700.30', '106700.30', '106304.10', '106415.90', '2821.384', 1747816199999, '300240460.76000', 46744, '1126.331', '119847154.76890', '0'], [1747816200000, '106416.00', '106499.10', '106322.20', '106361.70', '1313.441', 1747817099999, '139759489.65290', 29581, '590.449', '62827650.87300', '0']]
        self.rsi_6 = 0
        self.rsi_12 = 0
        self.rsi_14 = 0
        self.rsi_24 = 0

    def calculate(self):
        """
        计算RSI6、RSI12、RSI14、RSI24
        """
        close_prices = [float(item[4]) for item in self.kline_data]

        def rsi(period):
            if len(close_prices) < period + 1:
                return 0
            gains = []
            losses = []
            for i in range(-period, 0):
                diff = close_prices[i] - close_prices[i - 1]
                if diff > 0:
                    gains.append(diff)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(-diff)
            avg_gain = sum(gains) / period
            avg_loss = sum(losses) / period
            if avg_loss == 0:
                return 100
            rs = avg_gain / avg_loss
            return 100 - (100 / (1 + rs))

        self.rsi_6 = rsi(6)
        self.rsi_12 = rsi(12)
        self.rsi_14 = rsi(14)
        self.rsi_24 = rsi(24)
        return {
            "rsi6": self.rsi_6,
            "rsi12": self.rsi_12,
            "rsi14": self.rsi_14,
            "rsi24": self.rsi_24
        }
