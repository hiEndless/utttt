class SupportResistance:
    def __init__(self, kline_data):
        self.kline_data = kline_data  # [[timestamp, open, high, low, close, ...], ...]
        self.supports = []
        self.resistances = []

    def calculate(self):
        """
        以当前价格为基准，往上找3个阻力位R1>R2>R3，往下找3个支撑位S1>S2>S3
        """
        high_prices = [float(item[2]) for item in self.kline_data]
        low_prices = [float(item[3]) for item in self.kline_data]
        close = float(self.kline_data[-1][4])
        
        # 每50根K线为一个区间取一个极值
        interval = 60
        intervals = len(high_prices) // interval
        
        high = []
        low = []
        for i in range(intervals):
            start = i * interval
            end = (i + 1) * interval
            high.append(max(high_prices[start:end]))
            low.append(min(low_prices[start:end]))
        # 找到最近的3个阻力位和支撑位
        resistances = [p for p in sorted(high, reverse=True) if p > close][:3]
        supports = [p for p in sorted(low, reverse=True) if p < close][:3]
        # 补齐不足3个的情况
        while len(resistances) < 3:
            resistances.append(None)
        while len(supports) < 3:
            supports.append(None)
        self.resistances = resistances
        self.supports = supports
        return {
            "R1": resistances[0],
            "R2": resistances[1],
            "R3": resistances[2],
            "S1": supports[0],
            "S2": supports[1],
            "S3": supports[2]
        }

