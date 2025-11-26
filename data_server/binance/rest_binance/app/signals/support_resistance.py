class SupportResistance:
    def __init__(self, kline_data, interval=60):
        self.kline_data = kline_data
        self.supports = []
        self.resistances = []
        self.interval = interval

    def calculate(self):
        high_prices = [float(item[2]) for item in self.kline_data]
        low_prices = [float(item[3]) for item in self.kline_data]
        close = float(self.kline_data[-1][4])

        intervals = len(high_prices) // self.interval
        high, low = [], []

        for i in range(intervals):
            start = i * self.interval
            end = (i + 1) * self.interval
            high.append(max(high_prices[start:end]))
            low.append(min(low_prices[start:end]))

        # 去重
        high = list(dict.fromkeys(high))
        low = list(dict.fromkeys(low))

        # 阻力位从高到低
        resistances = [p for p in sorted(high, reverse=True) if p > close][:3]
        # 支撑位从高到低
        supports = [p for p in sorted(low, reverse=True) if p < close][:3]

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
