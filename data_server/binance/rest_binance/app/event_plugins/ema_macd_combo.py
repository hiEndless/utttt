from . import register_plugin
from .base import build_event, last_close


@register_plugin
class EMAMacdCombo:
    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []

        e = ind.get("ema", {})
        m = ind.get("macd", {})
        v = ind.get("vol", {})  # 用于ADX/ATR过滤

        pe = prev_ind.get("ema", {}) if prev_ind else {}
        pm = prev_ind.get("macd", {}) if prev_ind else {}

        ema12, ema26 = e.get("ema12"), e.get("ema26")
        dif, dea, hist = m.get("dif"), m.get("dea"), m.get("hist")

        # --- 基础检查 ---
        if ema12 is None or ema26 is None or dif is None or dea is None:
            return res

        prev_ema12, prev_ema26 = pe.get("ema12"), pe.get("ema26")
        prev_dif, prev_dea, prev_hist = pm.get("dif"), pm.get("dea"), pm.get("hist")

        if prev_ema12 is None or prev_ema26 is None or prev_dif is None or prev_dea is None:
            return res

        # --- 横盘过滤 ---
        close = last_close(kline)
        atr = v.get("atr")
        if close and atr and (atr / close) < 0.004:
            return res

        adx = v.get("adx")
        if adx is not None and adx < 20:
            return res

        # =============== 组合信号 ===============

        # --- Bullish 共振（EMA 金叉 + MACD 柱子加速 > 0） ---
        if prev_ema12 <= prev_ema26 and ema12 > ema26:
            # EMA 金叉成立

            # MACD 加速 or DIF 上穿 DEA
            macd_confirm = False
            if hist is not None and prev_hist is not None:
                macd_confirm = (hist > 0 and prev_hist <= 0)
            else:
                macd_confirm = (dif > dea and prev_dif <= prev_dea)

            if macd_confirm:
                res.append(build_event(
                    symbol, kline,
                    "ema_macd_combo_bull",
                    {"ema12": ema12, "ema26": ema26, "dif": dif, "dea": dea},
                    interval
                ))

        # --- Bearish 共振 ---
        if prev_ema12 >= prev_ema26 and ema12 < ema26:
            macd_confirm = False
            if hist is not None and prev_hist is not None:
                macd_confirm = (hist < 0 and prev_hist >= 0)
            else:
                macd_confirm = (dif < dea and prev_dif >= prev_dea)

            if macd_confirm:
                res.append(build_event(
                    symbol, kline,
                    "ema_macd_combo_bear",
                    {"ema12": ema12, "ema26": ema26, "dif": dif, "dea": dea},
                    interval
                ))

        return res
