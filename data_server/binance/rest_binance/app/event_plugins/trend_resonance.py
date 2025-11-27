from . import register_plugin
from .base import build_event, last_close


@register_plugin
class TrendResonancePlugin:
    min_adx = 25
    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []
        e = ind.get("ema", {})
        m = ind.get("ma", {})
        mc = ind.get("macd", {})
        v = ind.get("vol", {})
        b = ind.get("boll", {})
        close = last_close(kline)
        bull = 0
        bear = 0
        if e.get("ema12") is not None and e.get("ema26") is not None:
            if e["ema12"] > e["ema26"]:
                bull += 1
            if e["ema12"] < e["ema26"]:
                bear += 1
        if mc.get("dif") is not None and mc.get("dea") is not None:
            if mc["dif"] > mc["dea"]:
                bull += 1
            if mc["dif"] < mc["dea"]:
                bear += 1
        if m.get("ma20") and m.get("ma50") and m.get("ma200"):
            if m["ma20"] > m["ma50"] > m["ma200"]:
                bull += 1
            if m["ma20"] < m["ma50"] < m["ma200"]:
                bear += 1
        if b.get("middle_band") and close is not None:
            if close > b["middle_band"]:
                bull += 1
            if close < b["middle_band"]:
                bear += 1
        if v.get("adx") is not None and v["adx"] >= 25:
            if bull >= 3:
                res.append(build_event(symbol, kline, "trend_resonance", {"direction": "bullish", "score": bull}, interval))
            if bear >= 3:
                res.append(build_event(symbol, kline, "trend_resonance", {"direction": "bearish", "score": bear}, interval))
        return res