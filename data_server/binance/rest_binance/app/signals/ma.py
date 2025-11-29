
class MA:
    def __init__(self, kline_data):
        self.kline_data = kline_data  # [[1747815300000, '106700.30', '106700.30', '106304.10', '106415.90', '2821.384', 1747816199999, '300240460.76000', 46744, '1126.331', '119847154.76890', '0'], [1747816200000, '106416.00', '106499.10', '106322.20', '106361.70', '1313.441', 1747817099999, '139759489.65290', 29581, '590.449', '62827650.87300', '0']]
        self.ma_5 = 0  # 5日均线
        self.ma_10 = 0  # 10日均线
        self.ma_20 = 0  # 20日均线
        self.ma_50 = 0  # 50日均线
        self.ma_200 = 0  # 200日均线
    def calculate(self):
        """
        计算MA5、MA10、MA20、MA50、MA200均线
        """
        close_prices = [float(item[4]) for item in self.kline_data]
        def ma(n):
            if len(close_prices) < n:
                return 0
            return sum(close_prices[-n:]) / n
        self.ma_5 = ma(5)
        self.ma_10 = ma(10)
        self.ma_20 = ma(20)
        self.ma_50 = ma(50)
        self.ma_200 = ma(200)
        return {
            "ma5": self.ma_5,
            "ma10": self.ma_10,
            "ma20": self.ma_20,
            "ma50": self.ma_50,
            "ma200": self.ma_200
        }