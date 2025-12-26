from . import register_plugin
from .base import build_event, last_close, prev_close, CompositeComboBase


@register_plugin
class RSIMACDEMACombo(CompositeComboBase):
    """
    基于 CompositeComboBase 的三指标组合策略（RSI + EMA + MACD）
    包含：
    - 三联共振（最强）
    - RSI + EMA
    - RSI + MACD
    - EMA + MACD
    - RSI/MACD 背离
    """

    name = "rsi_ema_macd"
    version = "3.0"
    required_indicators = ["rsi", "ema", "macd"]

    bullish_signal = "rsi_ema_macd_combo_bullish"
    bearish_signal = "rsi_ema_macd_combo_bearish"

    # ============================================================
    #               取值函数：复用 CompositeComboBase 的 get_common_values
    # ============================================================
    def extract_all(self, ind, prev_ind):
        """提取策略需要的所有指标字段"""
        r = ind.get("rsi", {}) or {}
        pr = prev_ind.get("rsi", {}) if prev_ind else {}

        e = ind.get("ema", {}) or {}
        pe = prev_ind.get("ema", {}) if prev_ind else {}

        m = ind.get("macd", {}) or {}
        pm = prev_ind.get("macd", {}) if prev_ind else {}

        return {
            "rsi": r.get("rsi14"),
            "rsi_prev": pr.get("rsi14"),

            "ema5": e.get("ema5"),
            "ema12": e.get("ema12"),
            "ema26": e.get("ema26"),
            "ema5_prev": pe.get("ema5"),
            "ema12_prev": pe.get("ema12"),
            "ema26_prev": pe.get("ema26"),

            "dif": m.get("dif"),
            "dea": m.get("dea"),
            "hist": m.get("hist"),
            "dif_prev": pm.get("dif"),
            "dea_prev": pm.get("dea"),
            "hist_prev": pm.get("hist"),
        }

    # ============================================================
    #                        Bullish triggers
    # ============================================================
    def build_bullish_triggers(self, ind, prev_ind, kline):
        params = self._resolve_params(getattr(self, "_current_interval", ""))
        v = self.extract_all(ind, prev_ind)
        out = {}

        # -------- ① RSI 反弹 --------
        out["rsi_rebound"] = (
            v["rsi_prev"] is not None and v["rsi"] is not None and v["rsi_prev"] <= params.get("rsi_oversold", 30) < v["rsi"]
        )

        # -------- ② EMA 金叉 --------
        out["ema_golden_cross"] = (
            v["ema12_prev"] is not None
            and v["ema26_prev"] is not None
            and v["ema12"] is not None
            and v["ema26"] is not None
            and v["ema12_prev"] <= v["ema26_prev"]
            and v["ema12"] > v["ema26"]
        )

        # -------- ③ MACD 金叉 --------
        out["macd_golden_cross"] = (
            v["dif_prev"] is not None
            and v["dea_prev"] is not None
            and v["dif"] is not None
            and v["dea"] is not None
            and v["dif_prev"] <= v["dea_prev"]
            and v["dif"] > v["dea"]
        )

        # 来自 EMA+MACD 扩展策略的动能与零轴触发
        out["macd_hist_turn_positive"] = (
            v.get("hist_prev") is not None and v.get("hist") is not None and v["hist_prev"] <= 0 < v["hist"]
        )
        out["macd_signal_cross_up"] = (
            v["dif_prev"] is not None and v["dea_prev"] is not None and v["dif"] is not None and v["dea"] is not None and v["dif_prev"] <= v["dea_prev"] and v["dif"] > v["dea"]
        )
        out["dif_cross_zero_up"] = (
            v["dif_prev"] is not None and v["dif"] is not None and v["dif_prev"] <= 0 < v["dif"]
        )
        out["ema_triple_golden"] = (
            v.get("ema5_prev") is not None and v.get("ema12_prev") is not None and v.get("ema26_prev") is not None
            and v.get("ema5") is not None and v.get("ema12") is not None and v.get("ema26") is not None
            and v["ema5_prev"] <= v["ema12_prev"] <= v["ema26_prev"] and v["ema5"] > v["ema12"] > v["ema26"]
        )

        # -------- ④ RSI 超卖 + MACD 零轴下金叉 --------
        out["rsi_oversold_macd_zero_up"] = (
            v["rsi"] is not None and v["rsi"] < params.get("rsi_oversold", 30)
            and v["dif_prev"] is not None and v["dea_prev"] is not None and v["dif"] is not None and v["dea"] is not None
            and v["dif_prev"] <= v["dea_prev"] and v["dif"] > v["dea"] and v["dif"] < 0 and v["dea"] < 0
        )

        # -------- ⑤ RSI 突破 50 + DIF 上穿 0 轴 --------
        out["rsi50_dif_zero_break_up"] = (
            v["rsi_prev"] is not None and v["rsi"] is not None and v["dif_prev"] is not None and v["dif"] is not None
            and v["rsi_prev"] <= params.get("rsi_mid", 50) < v["rsi"] and v["dif_prev"] <= 0 < v["dif"]
        )

        # -------- ⑥ 顺趋势回踩（RSI 40-50 + DIF>DEA）--------
        out["rsi_pullback_bull"] = (
            v["rsi"] is not None and v["dif"] is not None and v["dea"] is not None
            and params.get("rsi_pullback_bull_low", 40) <= v["rsi"] <= params.get("rsi_pullback_bull_high", 50)
            and v["dif"] > v["dea"]
        )

        # -------- ⑦ RSI 极低反转 + MACD 柱子衰减 --------
        out["rsi_oversold_hist_decay_bull"] = (
            v["rsi"] is not None and v["rsi"] < params.get("rsi_oversold", 30)
        )

        # -------- ⑧ 强动能（RSI>70）--------
        out["rsi_strong_bull"] = (
            v["rsi"] is not None and v["rsi"] > params.get("rsi_overbought", 70)
        )

        return out

    # ============================================================
    #                        Bearish triggers
    # ============================================================
    def build_bearish_triggers(self, ind, prev_ind, kline):
        params = self._resolve_params(getattr(self, "_current_interval", ""))
        v = self.extract_all(ind, prev_ind)
        out = {}

        # -------- ① RSI 回落 --------
        out["rsi_fall"] = (
            v["rsi_prev"] is not None and v["rsi"] is not None and v["rsi_prev"] >= params.get("rsi_overbought", 70) > v["rsi"]
        )

        # -------- ② EMA 死叉 --------
        out["ema_death_cross"] = (
            v["ema12_prev"] is not None
            and v["ema26_prev"] is not None
            and v["ema12"] is not None
            and v["ema26"] is not None
            and v["ema12_prev"] >= v["ema26_prev"]
            and v["ema12"] < v["ema26"]
        )

        # -------- ③ MACD 死叉 --------
        out["macd_death_cross"] = (
            v["dif_prev"] is not None
            and v["dea_prev"] is not None
            and v["dif"] is not None
            and v["dea"] is not None
            and v["dif_prev"] >= v["dea_prev"]
            and v["dif"] < v["dea"]
        )

        # 来自 EMA+MACD 扩展策略的动能与零轴触发
        out["macd_hist_turn_negative"] = (
            v.get("hist_prev") is not None and v.get("hist") is not None and v["hist_prev"] >= 0 > v["hist"]
        )
        out["macd_signal_cross_down"] = (
            v["dif_prev"] is not None and v["dea_prev"] is not None and v["dif"] is not None and v["dea"] is not None and v["dif_prev"] >= v["dea_prev"] and v["dif"] < v["dea"]
        )
        out["dif_cross_zero_down"] = (
            v["dif_prev"] is not None and v["dif"] is not None and v["dif_prev"] >= 0 > v["dif"]
        )
        out["ema_triple_dead"] = (
            v.get("ema5_prev") is not None and v.get("ema12_prev") is not None and v.get("ema26_prev") is not None
            and v.get("ema5") is not None and v.get("ema12") is not None and v.get("ema26") is not None
            and v["ema5_prev"] >= v["ema12_prev"] >= v["ema26_prev"] and v["ema5"] < v["ema12"] < v["ema26"]
        )

        # -------- ④ RSI 超买 + MACD 零轴上死叉 --------
        out["rsi_overbought_macd_zero_down"] = (
            v["rsi"] is not None and v["rsi"] > params.get("rsi_overbought", 70)
            and v["dif_prev"] is not None and v["dea_prev"] is not None and v["dif"] is not None and v["dea"] is not None
            and v["dif_prev"] >= v["dea_prev"] and v["dif"] < v["dea"] and v["dif"] > 0 and v["dea"] > 0
        )

        # -------- ⑤ RSI 跌破 50 + DIF 下穿 0 轴 --------
        out["rsi50_dif_zero_break_down"] = (
            v["rsi_prev"] is not None and v["rsi"] is not None and v["dif_prev"] is not None and v["dif"] is not None
            and v["rsi_prev"] >= params.get("rsi_mid", 50) > v["rsi"] and v["dif_prev"] >= 0 > v["dif"]
        )

        # -------- ⑥ 顺趋势回踩（RSI 50–60 + DIF<DEA）--------
        out["rsi_pullback_bear"] = (
            v["rsi"] is not None and v["dif"] is not None and v["dea"] is not None
            and params.get("rsi_pullback_bear_low", 50) <= v["rsi"] <= params.get("rsi_pullback_bear_high", 60)
            and v["dif"] < v["dea"]
        )

        # -------- ⑦ RSI 过热反转 --------
        out["rsi_overbought_hist_decay_bear"] = (
            v["rsi"] is not None and v["rsi"] > params.get("rsi_overbought", 70)
        )

        # -------- ⑧ 强动能（RSI<30）--------
        out["rsi_strong_bear"] = (
            v["rsi"] is not None and v["rsi"] < params.get("rsi_oversold", 30)
        )

        return out

    # ============================================================
    #                        Bullish patterns（结构强信号）
    # ============================================================
    def build_bullish_patterns(self, ind, prev_ind, kline):
        v = self.extract_all(ind, prev_ind)
        close = last_close(kline)
        prev_close_value = prev_close(kline)

        out = {}

        # -------- RSI 底背离 --------
        out["rsi_bull_div"] = (
            close is not None and prev_close_value is not None and v["rsi"] is not None and v["rsi_prev"] is not None and
            close < prev_close_value and v["rsi"] > v["rsi_prev"]
        )

        # -------- MACD 底背离 --------
        out["macd_bull_div"] = (
            close is not None and prev_close_value is not None and v["dif"] is not None and v["dif_prev"] is not None and
            close < prev_close_value and v["dif"] > v["dif_prev"]
        )

        return out

    # ============================================================
    #                        Bearish patterns
    # ============================================================
    def build_bearish_patterns(self, ind, prev_ind, kline):
        v = self.extract_all(ind, prev_ind)
        close = last_close(kline)
        prev_close_value = prev_close(kline)

        out = {}

        # -------- RSI 顶背离 --------
        out["rsi_bear_div"] = (
            close is not None and prev_close_value is not None and v["rsi"] is not None and v["rsi_prev"] is not None and
            close > prev_close_value and v["rsi"] < v["rsi_prev"]
        )

        # -------- MACD 顶背离 --------
        out["macd_bear_div"] = (
            close is not None and prev_close_value is not None and v["dif"] is not None and v["dif_prev"] is not None and
            close > prev_close_value and v["dif"] < v["dif_prev"]
        )

        return out

    # ============================================================
    #                 optional: 给 payload 补充指标值
    # ============================================================
    def base_payload(self, ind, prev_ind, kline):
        """把主指标值放入事件 payload"""
        return self.extract_all(ind, prev_ind)
