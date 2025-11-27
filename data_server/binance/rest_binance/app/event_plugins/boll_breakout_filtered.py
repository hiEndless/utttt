from . import register_plugin
from .base import build_event, last_close


@register_plugin
class BollBreakoutFiltered:
    name = "boll_breakout_filtered"
    required_indicators = ["boll", "vol"]
    version = "1.2"
    min_adx = 25
    min_atr_ratio = 0.005

    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []
        b = ind.get("boll", {})
        v = ind.get("vol", {})

        upper, lower = b.get("upper_band"), b.get("lower_band")
        adx, atr = v.get("adx"), v.get("atr")
        close = last_close(kline)
        prev_close = float(kline[-2][4]) if len(kline) >= 2 else None

        # base safety
        if close is None or atr is None or adx is None:
            return []

        atr_ratio = atr / close if close else 0
        if atr_ratio < 0.005 or adx < 25:
            return []

        # breakout up
        if upper and prev_close and close > upper >= prev_close:
            res.append(build_event(symbol, kline, "boll_breakout_up_filtered", {
                "close": close,
                "upper": upper,
                "adx": adx,
                "atr_ratio": round(atr_ratio, 6),
            }, interval))

        # breakout down
        if lower and prev_close and close < lower <= prev_close:
            res.append(build_event(symbol, kline, "boll_breakout_down_filtered", {
                "close": close,
                "lower": lower,
                "adx": adx,
                "atr_ratio": round(atr_ratio, 6),
            }, interval))

        return res
