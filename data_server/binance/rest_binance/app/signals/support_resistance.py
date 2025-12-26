import pandas as pd
import ta


class SupportResistance:
    def __init__(self, kline_data, fractal_n=2, atr_window=14, cluster_coef=0.5):
        self.kline_data = kline_data
        self.fractal_n = int(fractal_n)
        self.atr_window = int(atr_window)
        self.cluster_coef = float(cluster_coef)
        self.supports = []
        self.resistances = []

    def _fractal_levels(self, highs, lows):
        n = self.fractal_n
        up = []
        down = []
        L = len(highs)
        for i in range(n, L - n):
            h = highs[i]
            l = lows[i]
            if h > max(highs[i - n:i]) and h > max(highs[i + 1:i + n + 1]):
                up.append(h)
            if l < min(lows[i - n:i]) and l < min(lows[i + 1:i + n + 1]):
                down.append(l)
        return up, down

    def _cluster(self, levels, threshold):
        if not levels:
            return []
        levels = sorted(levels)
        clusters = []
        cur = [levels[0]]
        for v in levels[1:]:
            if abs(v - cur[-1]) <= threshold:
                cur.append(v)
            else:
                clusters.append(cur)
                cur = [v]
        clusters.append(cur)
        centers = [sum(c) / len(c) for c in clusters]
        strengths = [len(c) for c in clusters]
        return list(zip(centers, strengths))

    def calculate(self):
        highs = [float(x[2]) for x in self.kline_data]
        lows = [float(x[3]) for x in self.kline_data]
        closes = [float(x[4]) for x in self.kline_data]
        close = closes[-1]
        h = pd.Series(highs)
        l = pd.Series(lows)
        c = pd.Series(closes)
        atr = ta.volatility.average_true_range(h, l, c, window=self.atr_window).iloc[-1]
        up, down = self._fractal_levels(highs, lows)
        threshold = max(atr * self.cluster_coef, 1e-8)
        up_clusters = self._cluster(up, threshold)
        down_clusters = self._cluster(down, threshold)
        ups = [v for v, _ in sorted(up_clusters, key=lambda x: (abs(x[0] - close), -x[1])) if v > close]
        downs = [v for v, _ in sorted(down_clusters, key=lambda x: (abs(x[0] - close), -x[1])) if v < close]
        resistances = ups[:3]
        supports = downs[:3]
        while len(resistances) < 3:
            resistances.append(None)
        while len(supports) < 3:
            supports.append(None)
        self.resistances = resistances
        self.supports = supports
        return {"R1": resistances[0], "R2": resistances[1], "R3": resistances[2], "S1": supports[0], "S2": supports[1],
                "S3": supports[2]}
