class EMA:
    def __init__(self, kline_data):
        self.kline_data = kline_data  # 二维K线数组
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

        self.ema_7 = self._calc_ema(closes, 7)
        self.ema_12 = self._calc_ema(closes, 12)
        self.ema_20 = self._calc_ema(closes, 20)
        self.ema_26 = self._calc_ema(closes, 26)
        self.ema_50 = self._calc_ema(closes, 50)
        self.ema_100 = self._calc_ema(closes, 100)
        self.ema_200 = self._calc_ema(closes, 200)

        return {
            "ema7": round(self.ema_7, 2) if self.ema_7 else None,
            "ema12": round(self.ema_12, 2) if self.ema_12 else None,
            "ema20": round(self.ema_20, 2) if self.ema_20 else None,
            "ema26": round(self.ema_26, 2) if self.ema_26 else None,
            "ema50": round(self.ema_50, 2) if self.ema_50 else None,
            "ema100": round(self.ema_100, 2) if self.ema_100 else None,
            "ema200": round(self.ema_200, 2) if self.ema_200 else None,
        }
