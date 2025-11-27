from . import register_plugin
from .base import build_event, last_close


@register_plugin
class RSIMACDCombo:
    name = "rsi_macd_combo"
    version = "2.0"
    required_indicators = ["rsi", "macd"]

    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []

        r = ind.get("rsi", {})
        p_r = prev_ind.get("rsi", {}) if prev_ind else {}

        m = ind.get("macd", {})
        p_m = prev_ind.get("macd", {}) if prev_ind else {}

        if (
            r.get("rsi14") is None or p_r.get("rsi14") is None or
            m.get("dif") is None or m.get("dea") is None or m.get("hist") is None or
            p_m.get("dif") is None or p_m.get("dea") is None or p_m.get("hist") is None
        ):
            return res

        rsi, rsi_prev = r["rsi14"], p_r["rsi14"]
        dif, dea, hist = m["dif"], m["dea"], m["hist"]
        dif_prev, dea_prev, hist_prev = p_m["dif"], p_m["dea"], p_m["hist"]

        # =============== 1. 经典反转 ===============
        if rsi_prev <= 30 < rsi and dif_prev <= dea_prev and dif > dea:
            res.append(build_event(symbol, kline, "rsi_macd_reversal_bull",
                                   {"rsi14": rsi, "dif": dif, "dea": dea}, interval))

        if rsi_prev >= 70 > rsi and dif_prev >= dea_prev and dif < dea:
            res.append(build_event(symbol, kline, "rsi_macd_reversal_bear",
                                   {"rsi14": rsi, "dif": dif, "dea": dea}, interval))

        # =============== 2. RSI超卖 + MACD 零轴下金叉 ===============
        if rsi < 30 and dif_prev <= dea_prev and dif > dea and dif < 0 and dea < 0:
            res.append(build_event(symbol, kline, "rsi_oversold_macd_zero_bull",
                                   {"rsi14": rsi, "dif": dif, "dea": dea}, interval))

        if rsi > 70 and dif_prev >= dea_prev and dif < dea and dif > 0 and dea > 0:
            res.append(build_event(symbol, kline, "rsi_overbought_macd_zero_bear",
                                   {"rsi14": rsi, "dif": dif, "dea": dea}, interval))

        # =============== 3. RSI 背离 + MACD 金叉/死叉确认 ===============
        if rsi > rsi_prev and hist > hist_prev and hist > 0 and dif > dea:
            res.append(build_event(symbol, kline, "rsi_macd_bull_divergence_confirm",
                                   {"rsi14": rsi, "hist": hist}, interval))

        if rsi < rsi_prev and hist < hist_prev and hist < 0 and dif < dea:
            res.append(build_event(symbol, kline, "rsi_macd_bear_divergence_confirm",
                                   {"rsi14": rsi, "hist": hist}, interval))

        # =============== 4. RSI 突破 50 + MACD 零轴突破 ===============
        if rsi_prev <= 50 < rsi and dif_prev <= 0 < dif:
            res.append(build_event(symbol, kline, "rsi50_macd_zero_break_bull",
                                   {"rsi14": rsi, "dif": dif}, interval))

        if rsi_prev >= 50 > rsi and dif_prev >= 0 > dif:
            res.append(build_event(symbol, kline, "rsi50_macd_zero_break_bear",
                                   {"rsi14": rsi, "dif": dif}, interval))

        # =============== 5. 顺趋势的 RSI 回踩确认 ===============
        if 40 <= rsi <= 50 and dif > dea:
            res.append(build_event(symbol, kline, "rsi_pullback_bull",
                                   {"rsi14": rsi, "dif": dif}, interval))

        if 50 <= rsi <= 60 and dif < dea:
            res.append(build_event(symbol, kline, "rsi_pullback_bear",
                                   {"rsi14": rsi, "dif": dif}, interval))

        # =============== 6. RSI 极值反转 + MACD 柱子衰减 ===============
        if rsi < 30 and hist > hist_prev:
            res.append(build_event(symbol, kline, "rsi_oversold_hist_decay_bull",
                                   {"rsi14": rsi, "hist": hist}, interval))

        if rsi > 70 and hist < hist_prev:
            res.append(build_event(symbol, kline, "rsi_overbought_hist_decay_bear",
                                   {"rsi14": rsi, "hist": hist}, interval))

        # =============== 7. 强动能突破（RSI > 70 + MACD 加速） ===============
        if rsi > 70 and hist > hist_prev > 0:
            res.append(build_event(symbol, kline, "rsi_strong_trend_bull",
                                   {"rsi14": rsi, "hist": hist}, interval))

        if rsi < 30 and hist < hist_prev < 0:
            res.append(build_event(symbol, kline, "rsi_strong_trend_bear",
                                   {"rsi14": rsi, "hist": hist}, interval))

        return res
