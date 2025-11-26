from . import register_plugin
from .base import build_event


@register_plugin
class RSIExtremePlugin:
    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []
        r = ind.get("rsi", {})
        pr = prev_ind.get("rsi", {}) if prev_ind else {}
        v = ind.get("vol", {})
        if r.get("rsi14") is not None and pr.get("rsi14") is not None and v.get("adx") is not None:
            if r["rsi14"] >= 80 and pr["rsi14"] < 80 and v["adx"] >= 20:
                res.append(build_event(symbol, kline, "rsi_overbought_filtered", {"value": r["rsi14"], "adx": v["adx"]}, interval))
            if r["rsi14"] <= 20 and pr["rsi14"] > 20 and v["adx"] >= 20:
                res.append(build_event(symbol, kline, "rsi_oversold_filtered", {"value": r["rsi14"], "adx": v["adx"]}, interval))
        return res