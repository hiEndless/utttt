from . import register_plugin
from .base import build_event, last_close


@register_plugin
class EMAMacdCombo:
    name = "ema_macd_extended_combo"
    version = "2.0"
    required_indicators = ["ema", "macd", "vol"]
    min_adx = 20

    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []

        # === 取指标 ===
        e = ind.get("ema", {})
        m = ind.get("macd", {})
        v = ind.get("vol", {})

        pe = prev_ind.get("ema", {}) if prev_ind else {}
        pm = prev_ind.get("macd", {}) if prev_ind else {}

        # EMAs
        ema5, ema12, ema26 = e.get("ema5"), e.get("ema12"), e.get("ema26")
        prev_ema5, prev_ema12, prev_ema26 = pe.get("ema5"), pe.get("ema12"), pe.get("ema26")

        # MACD
        dif, dea, hist = m.get("dif"), m.get("dea"), m.get("hist")
        prev_dif, prev_dea, prev_hist = pm.get("dif"), pm.get("dea"), pm.get("hist")

        # === 基础检查 ===
        if (
            ema12 is None or ema26 is None or
            dif is None or dea is None or
            prev_ema12 is None or prev_ema26 is None or
            prev_dif is None or prev_dea is None
        ):
            return res

        # === 横盘过滤：ATR、ADX ===
        close = last_close(kline)
        atr = v.get("atr")
        if close and atr and (atr / close) < 0.004:          # 波动率太低
            return res

        adx = v.get("adx")
        if adx is not None and adx < 20:                     # 无趋势
            return res

        # ===============================
        #  信号 1：EMA 金叉 + MACD 柱翻正（主多头）
        # ===============================
        if prev_ema12 <= prev_ema26 and ema12 > ema26:       # EMA 金叉
            macd_confirm = False
            if hist is not None and prev_hist is not None:
                macd_confirm = (hist > 0 and prev_hist <= 0)
            else:
                macd_confirm = (dif > dea and prev_dif <= prev_dea)

            if macd_confirm:
                res.append(build_event(
                    symbol, kline, "ema_macd_combo_bull",
                    {"ema12": ema12, "ema26": ema26, "dif": dif, "dea": dea},
                    interval
                ))

        # ===============================
        #  信号 2：EMA 死叉 + MACD 柱翻负（主空头）
        # ===============================
        if prev_ema12 >= prev_ema26 and ema12 < ema26:
            macd_confirm = False
            if hist is not None and prev_hist is not None:
                macd_confirm = (hist < 0 and prev_hist >= 0)
            else:
                macd_confirm = (dif < dea and prev_dif >= prev_dea)

            if macd_confirm:
                res.append(build_event(
                    symbol, kline, "ema_macd_combo_bear",
                    {"ema12": ema12, "ema26": ema26, "dif": dif, "dea": dea},
                    interval
                ))


        # ======================================================
        #  信号 3：EMA 金叉 + MACD 顶背离（趋势减弱 / 警告）
        # ======================================================
        # 条件：价格创新高 + DIF 未创新高
        prev_dif_high = pm.get("dif_high")
        if prev_dif_high and prev_ema12 <= prev_ema26 and ema12 > ema26:
            if dif < prev_dif_high:
                res.append(build_event(
                    symbol, kline, "ema_macd_bearish_divergence",
                    {"dif": dif, "prev_dif_high": prev_dif_high},
                    interval
                ))

        # ======================================================
        #  信号 4：EMA 死叉 + MACD 底背离（空头衰竭）
        # ======================================================
        prev_dif_low = pm.get("dif_low")
        if prev_dif_low and prev_ema12 >= prev_ema26 and ema12 < ema26:
            if dif > prev_dif_low:
                res.append(build_event(
                    symbol, kline, "ema_macd_bullish_divergence",
                    {"dif": dif, "prev_dif_low": prev_dif_low},
                    interval
                ))


        # ======================================================
        #  信号 5：EMA 金叉 + DIF 上穿 0 轴（趋势增强）
        # ======================================================
        if prev_ema12 <= prev_ema26 and ema12 > ema26:
            if prev_dif <= 0 < dif:
                res.append(build_event(
                    symbol, kline, "macd_zero_cross_bull",
                    {"dif": dif},
                    interval
                ))

        # ======================================================
        #  信号 6：EMA 死叉 + DIF 下穿 0 轴（空头增强）
        # ======================================================
        if prev_ema12 >= prev_ema26 and ema12 < ema26:
            if prev_dif >= 0 > dif:
                res.append(build_event(
                    symbol, kline, "macd_zero_cross_bear",
                    {"dif": dif},
                    interval
                ))


        # ======================================================
        #  信号 7：EMA 三金叉（ema5 > ema12 > ema26）+ DIF 金叉 DEA
        # ======================================================
        if ema5 and prev_ema5:
            if (
                prev_ema5 <= prev_ema12 <= prev_ema26 and
                ema5 > ema12 > ema26 and
                prev_dif <= prev_dea and dif > dea
            ):
                res.append(build_event(
                    symbol, kline, "ema_triple_bull",
                    {"ema5": ema5, "ema12": ema12, "ema26": ema26},
                    interval
                ))

        # ======================================================
        #  信号 8：EMA 三死叉（ema5 < ema12 < ema26）+ DIF 死叉 DEA
        # ======================================================
        if ema5 and prev_ema5:
            if (
                ema5 < ema12 < ema26 and
                prev_dif >= prev_dea and dif < dea
            ):
                res.append(build_event(
                    symbol, kline, "ema_triple_bear",
                    {"ema5": ema5, "ema12": ema12, "ema26": ema26},
                    interval
                ))


        # ======================================================
        #  信号 9：EMA 金叉后，MACD 连续两根绿柱缩短（加速转强）
        # ======================================================
        hist2 = pm.get("hist_prev2")
        if prev_hist is not None and hist is not None and hist2 is not None:
            if prev_ema12 <= prev_ema26 and ema12 > ema26:
                if abs(hist) < abs(prev_hist) < abs(hist2):
                    res.append(build_event(
                        symbol, kline, "macd_momentum_bull",
                        {"hist": hist},
                        interval
                    ))

        # ======================================================
        #  信号 10：EMA 死叉后，MACD 连续两根红柱缩短（空头衰竭）
        # ======================================================
        if prev_hist is not None and hist is not None and hist2 is not None:
            if prev_ema12 >= prev_ema26 and ema12 < ema26:
                if abs(hist) < abs(prev_hist) < abs(hist2):
                    res.append(build_event(
                        symbol, kline, "macd_momentum_bear",
                        {"hist": hist},
                        interval
                    ))

        return res
