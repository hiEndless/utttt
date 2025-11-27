from . import register_plugin
from .base import build_event, last_close


@register_plugin
class SRBreakFiltered:
    min_adx = 25
    min_atr_ratio = 0.01
    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []
        sr = ind.get("sr", {})
        v = ind.get("vol", {})
        close = last_close(kline)
        if close is None or v.get("adx") is None or v.get("atr") is None:
            return res
        ratio = (v["atr"] / close) if close != 0 else 0
        if sr.get("R1") is not None and close > sr["R1"] and v["adx"] >= 25 and ratio >= 0.01:
            res.append(build_event(symbol, kline, "resistance_break_filtered", {"level": sr["R1"], "close": close, "adx": v["adx"], "atr_ratio": round(ratio, 6)}, interval))
        if sr.get("S1") is not None and close < sr["S1"] and v["adx"] >= 25 and ratio >= 0.01:
            res.append(build_event(symbol, kline, "support_break_filtered", {"level": sr["S1"], "close": close, "adx": v["adx"], "atr_ratio": round(ratio, 6)}, interval))
        return res