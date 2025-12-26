
import math
import pandas as pd
import ta


class VolatilitySignal:
    def __init__(self, kline_data):
        self.kline_data = kline_data  # [[timestamp, open, high, low, close], ...]
        self.volatility = 0          # 年化波动率
        self.atr = 0                 # ATR
        self.dmi_plus = 0            # DMI+
        self.dmi_minus = 0           # DMI-
        self.adx = 0                 # ADX

    def calculate(self, period=14):
        if len(self.kline_data) < period + 1:
            raise ValueError("K线数据不足以计算指标")
        high_prices = [float(item[2]) for item in self.kline_data]
        low_prices = [float(item[3]) for item in self.kline_data]
        close_prices = [float(item[4]) for item in self.kline_data]
        self._calculate_volatility(close_prices, period)
        h = pd.Series(high_prices)
        l = pd.Series(low_prices)
        c = pd.Series(close_prices)
        atr_series = ta.volatility.average_true_range(h, l, c, window=period)
        adi = ta.trend.ADXIndicator(high=h, low=l, close=c, window=period)
        self.atr = float(atr_series.iloc[-1])
        self.dmi_plus = float(adi.adx_pos().iloc[-1])
        self.dmi_minus = float(adi.adx_neg().iloc[-1])
        self.adx = float(adi.adx().iloc[-1])
        return {
            "volatility": self.volatility,
            "atr": self.atr,
            "dmi_plus": self.dmi_plus,
            "dmi_minus": self.dmi_minus,
            "adx": self.adx,
        }

    def __calculate_volatility(self, close_prices, period=14):
        """计算日化波动率（基于收盘价的对数收益率标准差）"""
        n = period
        if len(close_prices) < n + 1:
            raise ValueError("K线数据不足以计算波动率和相关指标")
        # 波动率（标准差/均值）
        window = close_prices[-n:]
        mean = sum(window) / n
        std = (sum([(x - mean) ** 2 for x in window]) / n) ** 0.5
        self.volatility = std / mean if mean != 0 else 0

    def _calculate_volatility(self, close_prices, period=14):
        """计算日化波动率（基于收盘价的对数收益率标准差）"""
        if len(close_prices) < 2:
            self.volatility = 0
            return

        log_returns = []
        for i in range(1, len(close_prices)):
            if close_prices[i - 1] == 0:
                log_returns.append(0)
            else:
                log_returns.append(math.log(close_prices[i] / close_prices[i - 1]))

        recent_returns = log_returns[-period:] if len(log_returns) >= period else log_returns
        if not recent_returns:
            self.volatility = 0
            return

        mean = sum(recent_returns) / len(recent_returns)
        variance = sum((r - mean) ** 2 for r in recent_returns) / len(recent_returns)
        std_dev = math.sqrt(variance)

        # 修改点：不再年化，直接使用日标准差
        self.volatility = std_dev

    def _calculate_atr(self, high_prices, low_prices, close_prices, period):
        """计算ATR（使用Wilder平滑）"""
        trs = []
        for i in range(1, len(close_prices)):
            tr = max(
                high_prices[i] - low_prices[i],
                abs(high_prices[i] - close_prices[i - 1]),
                abs(low_prices[i] - close_prices[i - 1])
            )
            trs.append(tr)

        if len(trs) < period:
            self.atr = 0
            return

        # 初始ATR
        wilder_atr = sum(trs[:period]) / period
        for i in range(period, len(trs)):
            wilder_atr = (wilder_atr * (period - 1) + trs[i]) / period

        self.atr = wilder_atr

    def _calculate_dmi(self, high_prices, low_prices, close_prices, period):
        """计算DMI+/-，返回DI+/-的历史序列"""
        plus_dms = []
        minus_dms = []
        trs = []

        for i in range(1, len(close_prices)):
            up_move = high_prices[i] - high_prices[i - 1]
            down_move = low_prices[i - 1] - low_prices[i]

            plus_dms.append(up_move if up_move > down_move and up_move > 0 else 0)
            minus_dms.append(down_move if down_move > up_move and down_move > 0 else 0)

            tr = max(
                high_prices[i] - low_prices[i],
                abs(high_prices[i] - close_prices[i - 1]),
                abs(low_prices[i] - close_prices[i - 1])
            )
            trs.append(tr)

        if len(trs) < period:
            return [], []

        # 初始平滑值
        avg_tr = sum(trs[:period]) / period
        avg_plus_dm = sum(plus_dms[:period]) / period
        avg_minus_dm = sum(minus_dms[:period]) / period

        di_plus_list = []
        di_minus_list = []

        for i in range(period, len(trs)):
            avg_tr = (avg_tr * (period - 1) + trs[i]) / period
            avg_plus_dm = (avg_plus_dm * (period - 1) + plus_dms[i]) / period
            avg_minus_dm = (avg_minus_dm * (period - 1) + minus_dms[i]) / period

            di_plus = (avg_plus_dm / avg_tr) * 100 if avg_tr != 0 else 0
            di_minus = (avg_minus_dm / avg_tr) * 100 if avg_tr != 0 else 0

            di_plus_list.append(di_plus)
            di_minus_list.append(di_minus)

        self.dmi_plus = di_plus_list[-1] if di_plus_list else 0
        self.dmi_minus = di_minus_list[-1] if di_minus_list else 0

        return di_plus_list, di_minus_list

    def _calculate_adx(self, di_plus_list, di_minus_list, period):
        """计算ADX（基于DI+/-历史序列）"""
        if len(di_plus_list) < period:
            self.adx = 0
            return

        dx_list = []
        for i in range(len(di_plus_list)):
            total = di_plus_list[i] + di_minus_list[i]
            if total == 0:
                dx = 0
            else:
                dx = abs(di_plus_list[i] - di_minus_list[i]) / total * 100
            dx_list.append(dx)

        if len(dx_list) < period:
            self.adx = 0
            return

        # 初始ADX
        adx = sum(dx_list[:period]) / period
        for i in range(period, len(dx_list)):
            adx = (adx * (period - 1) + dx_list[i]) / period

        self.adx = adx
