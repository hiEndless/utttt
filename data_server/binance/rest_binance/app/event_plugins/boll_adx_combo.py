from . import register_plugin
from .base import build_event, last_close


@register_plugin
class BollADXCombo:
    name = "boll_adx_combo"
    version = "1.1"
    required_indicators = ["boll", "vol"]

    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []
        b = ind.get("boll", {})
        v = ind.get("vol", {})
        close = last_close(kline)
        prev_close = float(kline[-2][4]) if len(kline) >= 2 else None

        if close is None or prev_close is None:
            return res

        upper, lower = b.get("upper_band"), b.get("lower_band")
        adx = v.get("adx")

        if upper is None or lower is None or adx is None:
            return res

        # --- 组合过滤条件 ---
        # 1) 强趋势
        if adx <= 25:
            return res

        # 2) 带宽过滤（避免假突破）
        mid = b.get("middle_band")
        if mid:
            band_width = (upper - lower) / mid
            if band_width < 0.015:
                return res

        # --- 上轨突破 ---
        if prev_close <= upper < close:
            res.append(build_event(
                symbol,
                kline,
                "strong_breakout_up",
                {"close": close, "upper": upper, "adx": adx},
                interval
            ))

        # --- 下轨突破 ---
        if prev_close >= lower > close:
            res.append(build_event(
                symbol,
                kline,
                "strong_breakout_down",
                {"close": close, "lower": lower, "adx": adx},
                interval
            ))

        return res
