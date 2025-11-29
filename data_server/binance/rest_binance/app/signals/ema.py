class EMA:
    def __init__(self, kline_data):
        self.kline_data = kline_data  # 二维K线数组
        self.ema_5 = None
        self.ema_7 = None
        self.ema_12 = None
        self.ema_20 = None
        self.ema_26 = None
        self.ema_50 = None
        self.ema_100 = None
        self.ema_200 = None

    def _calc_ema(self, prices, n):
        """
        计算 EMA(n)
        prices: 收盘价列表
        n: 周期
        """
        if len(prices) < n:
            return None  # 数据不足

        k = 2 / (n + 1)

        # 第一个 EMA 为 SMA（前 n 根取平均）
        ema_prev = sum(prices[:n]) / n

        # 从第 n 根之后开始逐步迭代
        for price in prices[n:]:
            ema_prev = (price - ema_prev) * k + ema_prev

        return ema_prev

    def calculate(self):
        """
        计算多个常用 EMA
        """
        closes = [float(item[4]) for item in self.kline_data]

        self.ema_5 = self._calc_ema(closes, 5)
        self.ema_7 = self._calc_ema(closes, 7)
        self.ema_12 = self._calc_ema(closes, 12)
        self.ema_20 = self._calc_ema(closes, 20)
        self.ema_26 = self._calc_ema(closes, 26)
        self.ema_50 = self._calc_ema(closes, 50)
        self.ema_100 = self._calc_ema(closes, 100)
        self.ema_200 = self._calc_ema(closes, 200)

        return {
            "ema5": self.ema_5 if self.ema_5 is not None else None,
            "ema7": self.ema_7 if self.ema_7 is not None else None,
            "ema12": self.ema_12 if self.ema_12 is not None else None,
            "ema20": self.ema_20 if self.ema_20 is not None else None,
            "ema26": self.ema_26 if self.ema_26 is not None else None,
            "ema50": self.ema_50 if self.ema_50 is not None else None,
            "ema100": self.ema_100 if self.ema_100 is not None else None,
            "ema200": self.ema_200 if self.ema_200 is not None else None,
        }
