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

    name = "triple_rsi_ema_macd"
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

            "ema12": e.get("ema12"),
            "ema26": e.get("ema26"),
            "ema12_prev": pe.get("ema12"),
            "ema26_prev": pe.get("ema26"),

            "dif": m.get("dif"),
            "dea": m.get("dea"),
            "dif_prev": pm.get("dif"),
            "dea_prev": pm.get("dea"),
        }

    # ============================================================
    #                        Bullish triggers
    # ============================================================
    def build_bullish_triggers(self, ind, prev_ind, kline):
        v = self.extract_all(ind, prev_ind)
        out = {}

        # -------- ① RSI 反弹 --------
        out["rsi_rebound"] = (
            v["rsi_prev"] is not None and v["rsi"] is not None and v["rsi_prev"] <= 30 < v["rsi"]
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

        return out

    # ============================================================
    #                        Bearish triggers
    # ============================================================
    def build_bearish_triggers(self, ind, prev_ind, kline):
        v = self.extract_all(ind, prev_ind)
        out = {}

        # -------- ① RSI 回落 --------
        out["rsi_fall"] = (
            v["rsi_prev"] is not None and v["rsi"] is not None and v["rsi_prev"] >= 70 > v["rsi"]
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

        return out

    # ============================================================
    #                        Bullish patterns（结构强信号）
    # ============================================================
    def build_bullish_patterns(self, ind, prev_ind, kline):
        v = self.extract_all(ind, prev_ind)
        close = last_close(kline)
        prev_close = prev_close(kline)

        out = {}

        # -------- RSI 底背离 --------
        out["rsi_bull_div"] = (
            close is not None and prev_close is not None and v["rsi"] is not None and v["rsi_prev"] is not None and
            close < prev_close and v["rsi"] > v["rsi_prev"]
        )

        # -------- MACD 底背离 --------
        out["macd_bull_div"] = (
            close is not None and prev_close is not None and v["dif"] is not None and v["dif_prev"] is not None and
            close < prev_close and v["dif"] > v["dif_prev"]
        )

        return out

    # ============================================================
    #                        Bearish patterns
    # ============================================================
    def build_bearish_patterns(self, ind, prev_ind, kline):
        v = self.extract_all(ind, prev_ind)
        close = last_close(kline)
        prev_close = prev_close(kline)

        out = {}

        # -------- RSI 顶背离 --------
        out["rsi_bear_div"] = (
            close is not None and prev_close is not None and v["rsi"] is not None and v["rsi_prev"] is not None and
            close > prev_close and v["rsi"] < v["rsi_prev"]
        )

        # -------- MACD 顶背离 --------
        out["macd_bear_div"] = (
            close is not None and prev_close is not None and v["dif"] is not None and v["dif_prev"] is not None and
            close > prev_close and v["dif"] < v["dif_prev"]
        )

        return out

    # ============================================================
    #                 optional: 给 payload 补充指标值
    # ============================================================
    def base_payload(self, ind, prev_ind, kline):
        """把主指标值放入事件 payload"""
        return self.extract_all(ind, prev_ind)

