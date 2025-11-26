from . import register_plugin
from .base import build_event, last_close


@register_plugin
class RSIMACDCombo:
    name = "rsi_macd_reversal"
    version = "1.0"
    required_indicators = ["rsi", "macd"]

    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []
        r = ind.get("rsi", {})
        p_r = prev_ind.get("rsi", {}) if prev_ind else {}

        m = ind.get("macd", {})
        p_m = prev_ind.get("macd", {}) if prev_ind else {}

        # 边界检查
        if (
            r.get("rsi14") is None or p_r.get("rsi14") is None or
            m.get("dif") is None or m.get("dea") is None or
            p_m.get("dif") is None or p_m.get("dea") is None
        ):
            return res

        rsi = r["rsi14"]
        rsi_prev = p_r["rsi14"]

        dif, dea = m["dif"], m["dea"]
        dif_prev, dea_prev = p_m["dif"], p_m["dea"]

        # ---- 多头反转 ----
        if rsi_prev <= 30 < rsi and dif_prev <= dea_prev and dif > dea:
            res.append(build_event(
                symbol, kline, "rsi_macd_combo_reversal",
                {
                    "direction": "bullish",
                    "rsi14": rsi,
                    "dif": dif,
                    "dea": dea
                },
                interval
            ))

        # ---- 空头反转 ----
        if rsi_prev >= 70 > rsi and dif_prev >= dea_prev and dif < dea:
            res.append(build_event(
                symbol, kline, "rsi_macd_combo_reversal",
                {
                    "direction": "bearish",
                    "rsi14": rsi,
                    "dif": dif,
                    "dea": dea
                },
                interval
            ))

        return res
