from . import register_plugin
from .base import build_event, last_close, prev_close, CompositeComboBase


@register_plugin
class RSIMACDCombo(CompositeComboBase):
    name = "rsi_macd_combo"
    version = "3.0"
    required_indicators = ["rsi", "macd"]
    supported_intervals = []

    bullish_signal = "rsi_macd_bullish"
    bearish_signal = "rsi_macd_bearish"

    # ------------------------------
    #   Bullish Triggers（快信号）
    # ------------------------------
    def build_bullish_triggers(self, ind, prev_ind, kline):
        params = self._resolve_params(getattr(self, "_current_interval", ""))
        r = ind.get("rsi", {})
        m = ind.get("macd", {})

        pr = prev_ind.get("rsi", {}) if prev_ind else {}
        pm = prev_ind.get("macd", {}) if prev_ind else {}

        rsi = r.get("rsi14")
        rsi_prev = pr.get("rsi14")

        dif, dea, hist = m.get("dif"), m.get("dea"), m.get("hist")
        dif_prev, dea_prev, hist_prev = pm.get("dif"), pm.get("dea"), pm.get("hist")

        if None in (rsi, rsi_prev, dif, dea, hist, dif_prev, dea_prev, hist_prev):
            return {}

        return {
            # 1. 经典 RSI 反转 + MACD 金叉
            "rsi_macd_reversal": (rsi_prev <= params.get("rsi_oversold", 30) < rsi and dif_prev <= dea_prev and dif > dea),

            # 2. RSI 超卖 + MACD 零轴下金叉
            "rsi_oversold_macd_zero": (rsi < params.get("rsi_oversold", 30) and dif_prev <= dea_prev and dif > dea and dif < 0 and dea < 0),

            # 4. RSI 突破50 + DIF 突破 0 轴
            "rsi50_macd_zero_break": (rsi_prev <= params.get("rsi_mid", 50) < rsi and dif_prev <= 0 < dif),

            # 5. 顺趋势回踩（RSI 40-50 + DIF>DEA）
            "rsi_pullback_bull": (params.get("rsi_pullback_bull_low", 40) <= rsi <= params.get("rsi_pullback_bull_high", 50) and dif > dea),

            # 6. RSI 极低反转 + MACD 柱子衰减
            "rsi_oversold_hist_decay": (rsi < params.get("rsi_oversold", 30) and hist > hist_prev),

            # 7. 强动能（RSI>70 + hist 加速）
            "rsi_strong_bull": (rsi > params.get("rsi_overbought", 70) and hist > hist_prev > 0),
        }

    # ------------------------------
    #   Bearish Triggers
    # ------------------------------
    def build_bearish_triggers(self, ind, prev_ind, kline):
        params = self._resolve_params(getattr(self, "_current_interval", ""))
        r = ind.get("rsi", {})
        m = ind.get("macd", {})

        pr = prev_ind.get("rsi", {}) if prev_ind else {}
        pm = prev_ind.get("macd", {}) if prev_ind else {}

        rsi = r.get("rsi14")
        rsi_prev = pr.get("rsi14")

        dif, dea, hist = m.get("dif"), m.get("dea"), m.get("hist")
        dif_prev, dea_prev, hist_prev = pm.get("dif"), pm.get("dea"), pm.get("hist")

        if None in (rsi, rsi_prev, dif, dea, hist, dif_prev, dea_prev, hist_prev):
            return {}

        return {
            # 1. 经典 RSI 回落 + MACD 死叉
            "rsi_macd_reversal_bear": (rsi_prev >= params.get("rsi_overbought", 70) > rsi and dif_prev >= dea_prev and dif < dea),

            # 2. RSI 超买 + MACD 零轴上死叉
            "rsi_overbought_macd_zero": (rsi > params.get("rsi_overbought", 70) and dif_prev >= dea_prev and dif < dea and dif > 0 and dea > 0),

            # 4. RSI 跌破 50 + DIF 跌破 0 轴
            "rsi50_macd_zero_break_bear": (rsi_prev >= params.get("rsi_mid", 50) > rsi and dif_prev >= 0 > dif),

            # 5. 顺趋势回踩（RSI 50–60 + DIF < DEA）
            "rsi_pullback_bear": (params.get("rsi_pullback_bear_low", 50) <= rsi <= params.get("rsi_pullback_bear_high", 60) and dif < dea),

            # 6. RSI 过热反转 + MACD 柱子衰减
            "rsi_overbought_hist_decay": (rsi > params.get("rsi_overbought", 70) and hist < hist_prev),

            # 7. 强动能（RSI<30 + hist 加速）
            "rsi_strong_bear": (rsi < params.get("rsi_oversold", 30) and hist < hist_prev < 0),
        }

    # ------------------------------
    #  Patterns（结构信号：背离）
    # ------------------------------
    def build_bullish_patterns(self, ind, prev_ind, kline):
        if not prev_ind:
            return {}

        r = ind.get("rsi", {})
        pr = prev_ind.get("rsi", {})

        m = ind.get("macd", {})
        pm = prev_ind.get("macd", {})

        rsi = r.get("rsi14")
        rsi_prev = pr.get("rsi14")

        dif, hist = m.get("dif"), m.get("hist")
        dif_prev, hist_prev = pm.get("dif"), pm.get("hist")

        if None in (rsi, rsi_prev, dif, dif_prev, hist, hist_prev):
            return {}

        close = last_close(kline)
        prev_c = prev_close(kline)

        return {
            # RSI 底背离
            "rsi_bull_divergence": (close is not None and prev_c is not None and rsi is not None and rsi_prev is not None and close < prev_c and rsi > rsi_prev),

            # MACD 底背离
            "macd_bull_divergence": (close is not None and prev_c is not None and dif is not None and dif_prev is not None and close < prev_c and dif > dif_prev),
        }

    def build_bearish_patterns(self, ind, prev_ind, kline):
        if not prev_ind:
            return {}

        r = ind.get("rsi", {})
        pr = prev_ind.get("rsi", {})

        m = ind.get("macd", {})
        pm = prev_ind.get("macd", {})

        rsi = r.get("rsi14")
        rsi_prev = pr.get("rsi14")

        dif, dea = m.get("dif"), m.get("dea")
        dif_prev, dea_prev = pm.get("dif"), pm.get("dea")

        if None in (rsi, rsi_prev, dif, dif_prev):
            return {}

        close = last_close(kline)
        prev_c = prev_close(kline)

        return {
            # RSI 顶背离
            "rsi_bear_divergence": (close is not None and prev_c is not None and rsi is not None and rsi_prev is not None and close > prev_c and rsi < rsi_prev),

            # MACD 顶背离
            "macd_bear_divergence": (close is not None and prev_c is not None and dif is not None and dif_prev is not None and close > prev_c and dif < dif_prev),
        }

    # ------------------------------
    #  Payload 可选增强（附加字段）
    # ------------------------------
    def base_payload(self, ind, prev_ind, kline):
        r = ind.get("rsi", {})
        m = ind.get("macd", {})

        return {
            "rsi14": r.get("rsi14"),
            "dif": m.get("dif"),
            "dea": m.get("dea"),
            "hist": m.get("hist"),
        }
