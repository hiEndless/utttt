from . import register_plugin
from .base import build_event, last_close


@register_plugin
class BollVolCombo:
    name = "boll_vol_combo"
    version = "2.0"
    required_indicators = ["boll", "vol", "atr"]

    def generate(self, symbol, kline, ind, prev_ind, interval):
        """
        扩展BOLL+VOL策略组合：
        - 上轨突破 + 成交量放大 => 强突破上
        - 下轨突破 + 成交量放大 => 强突破下
        - 中轨支撑回踩 + 成交量缩小 => 回调买入信号
        - 带宽极窄 + ATR突破 => 突破信号
        """
        res = []
        b = ind.get("boll", {})
        v = ind.get("vol", {})
        atr = ind.get("atr")
        close = last_close(kline)
        prev_close = float(kline[-2][4]) if len(kline) >= 2 else None
        prev_vol = float(kline[-2][5]) if len(kline) >= 2 else None
        current_vol = float(kline[-1][5]) if len(kline) >= 1 else None

        if None in (close, prev_close, prev_vol, current_vol, atr):
            return res

        upper, lower, mid = b.get("upper_band"), b.get("lower_band"), b.get("middle_band")
        if None in (upper, lower, mid):
            return res

        # --- 带宽计算 ---
        band_width = (upper - lower) / mid if mid else 0

        # --- 上轨突破 ---
        if prev_close <= upper < close and current_vol > prev_vol:
            res.append(build_event(
                symbol,
                kline,
                "breakout_up_vol",
                {"close": close, "upper": upper, "vol": current_vol},
                interval
            ))

        # --- 下轨突破 ---
        if prev_close >= lower > close and current_vol > prev_vol:
            res.append(build_event(
                symbol,
                kline,
                "breakout_down_vol",
                {"close": close, "lower": lower, "vol": current_vol},
                interval
            ))

        # --- 中轨回踩（支撑回调） ---
        if lower < close < mid and prev_close > mid and current_vol < prev_vol:
            res.append(build_event(
                symbol,
                kline,
                "midband_pullback",
                {"close": close, "middle": mid, "vol": current_vol},
                interval
            ))

        # --- 带宽极窄 + ATR突破（震荡突破信号） ---
        if band_width < 0.02:  # 可调节收窄阈值
            if close - prev_close > atr:
                res.append(build_event(
                    symbol,
                    kline,
                    "atr_breakout_up",
                    {"close": close, "band_width": band_width, "atr": atr},
                    interval
                ))
            elif prev_close - close > atr:
                res.append(build_event(
                    symbol,
                    kline,
                    "atr_breakout_down",
                    {"close": close, "band_width": band_width, "atr": atr},
                    interval
                ))

        # --- 成交量异常（放大/缩小） ---
        vol_ratio = current_vol / prev_vol if prev_vol else 1
        if vol_ratio > 1.5:
            res.append(build_event(
                symbol,
                kline,
                "vol_spike",
                {"close": close, "vol": current_vol, "ratio": vol_ratio},
                interval
            ))
        elif vol_ratio < 0.5:
            res.append(build_event(
                symbol,
                kline,
                "vol_drop",
                {"close": close, "vol": current_vol, "ratio": vol_ratio},
                interval
            ))

        return res
