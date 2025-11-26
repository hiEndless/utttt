from signals import EMA, MA, MACD, RSI, KDJ, BollingerBandSignal, VolatilitySignal, SupportResistance


def signals(self, symbol: str, interval: str, limit: int = 200):
    klines_data = self.klines(symbol, interval, limit)
    bolling = BollingerBandSignal(klines_data).calculate()
    ema = EMA(klines_data).calculate()
    ma = MA(klines_data).calculate()
    rsi = RSI(klines_data).calculate()
    macd = MACD(klines_data).calculate()
    kdj = KDJ(klines_data).calculate()
    support_resistance = SupportResistance(klines_data).calculate()
    volatility = VolatilitySignal(klines_data).calculate()
    return bolling, ema, ma, rsi, macd, kdj, support_resistance, volatility, klines_data


# -----------------------------
# 事件生成器
# -----------------------------
class EventGenerator:
    def __init__(self, kline, interval):
        self.ind = signals(kline, interval)
        self.events = []

    def generate_events(self):
        self.events = []
        # MA/EMA趋势事件
        ma5 = self.ind.ma(5)
        ma20 = self.ind.ma(20)
        ema12 = self.ind.ema(12)
        ema26 = self.ind.ema(26)
        if ma5 and ma20:
            if ma5 > ma20:
                self.events.append({"type": "MA5_above_MA20", "direction": "up", "strength": 1})
            else:
                self.events.append({"type": "MA5_below_MA20", "direction": "down", "strength": 1})
        if ema12 and ema26:
            if ema12 > ema26:
                self.events.append({"type": "EMA12_above_EMA26", "direction": "up", "strength": 1})
            else:
                self.events.append({"type": "EMA12_below_EMA26", "direction": "down", "strength": 1})

        # RSI超买/超卖
        rsi = self.ind.rsi()
        if rsi:
            if rsi > 70:
                self.events.append({"type": "RSI_overbought", "direction": "down", "strength": 1})
            elif rsi < 30:
                self.events.append({"type": "RSI_oversold", "direction": "up", "strength": 1})

        # Boll突破
        boll_upper, boll_mid, boll_lower = self.ind.boll()
        last_close = self.ind.close[-1]
        if last_close > boll_upper:
            self.events.append({"type": "Boll_break_upper", "direction": "up", "strength": 1})
        elif last_close < boll_lower:
            self.events.append({"type": "Boll_break_lower", "direction": "down", "strength": 1})

        # MACD
        macd_line, signal_line, hist = self.ind.macd()
        if macd_line and signal_line:
            if macd_line > signal_line:
                self.events.append({"type": "MACD_bullish", "direction": "up", "strength": 1})
            else:
                self.events.append({"type": "MACD_bearish", "direction": "down", "strength": 1})

        # KDJ
        k, d, j = self.ind.kdj()
        if j > 80:
            self.events.append({"type": "KDJ_overbought", "direction": "down", "strength": 0.5})
        elif j < 20:
            self.events.append({"type": "KDJ_oversold", "direction": "up", "strength": 0.5})

        # Volatility
        vol = self.ind.volatility()
        if vol and vol > np.mean(self.ind.close[-14:]) * 0.02:  # 波动率大于2%则高波动
            self.events.append({"type": "High_volatility", "direction": "neutral", "strength": 0.5})

        # -----------------------------
        # 可扩展：50+事件模板，可按需求增加
        # -----------------------------
        # 1. EMA金叉/死叉
        # 2. MA多头排列/空头排列
        # 3. RSI超买/超卖
        # 4. KDJ高低位反转
        # 5. MACD背离
        # 6. Boll带突破
        # 7. 波动率异常
        # 8. 上影线/下影线异常
        # 9. 支撑/阻力突破
        # 10. 均线拐点
        # 11-50 可组合以上形成事件，如趋势加强、弱反转、回调机会、短期突破等

        return self.events


# -----------------------------
# 使用示例
# -----------------------------
if __name__ == "__main__":
    sample_kline = [
        [1747815300000, '106700.30', '106700.30', '106304.10', '106415.90', '2821.384', 1747816199999,
         '300240460.76000', 46744, '1126.331', '119847154.76890', '0'],
        [1747816200000, '106416.00', '106499.10', '106322.20', '106361.70', '1313.441', 1747817099999,
         '139759489.65290', 29581, '590.449', '62827650.87300', '0']
    ]

    generator = EventGenerator(sample_kline)
    events = generator.generate_events()
    for e in events:
        print(e)
