from . import register_plugin
from .base import last_close, prev_close, CompositeComboBase


# RSIKDJVOLCombo v4 — 基于 CompositeComboBase 的具体实现
@register_plugin
class RSIKDJVOLCombo(CompositeComboBase):
    """
    RSI + KDJ + VOL 组合（V4）
    - 使用基类的 get_common_values/base_filters/compute_strength
    - triggers 与 patterns 更清晰、无重复
    """

    name = "rsi_kdj_combo"
    version = "4.0"
    required_indicators = ["rsi", "kdj", "vol"]

    bullish_signal = "rsi_kdj_bullish"
    bearish_signal = "rsi_kdj_bearish"

    # 可覆盖父类默认阈值（按策略需要微调）
    atr_ratio_threshold = 0.0035
    adx_threshold = 18
    vol_ratio_threshold = 1.35
    min_strength = 2
    trigger_weight = 1
    pattern_weight = 2

    def base_payload(self, ind, prev_ind, kline):
        common = self.get_common_values(ind, prev_ind, kline)
        return {"rsi14": common.get("rsi14"), "rsi6": common.get("rsi6"),
                "k": common.get("k"), "d": common.get("d"), "j": common.get("j")}

    def choose_direction(self, ind, prev_ind, kline):
        # 更稳健的方向判断：结合中轴（50）和 K/D 关系
        common = self.get_common_values(ind, prev_ind, kline)
        rsi = common.get("rsi14")
        prev_rsi = common.get("prev_rsi14")
        k = common.get("k")
        d = common.get("d")

        up = False
        down = False
        # RSI 动量方向
        if rsi is not None and prev_rsi is not None:
            if rsi > prev_rsi and rsi >= 45:
                up = True
            if rsi < prev_rsi and rsi <= 55:
                down = True
        # KDJ 方向
        if k is not None and d is not None:
            if k > d and k >= 45:
                up = True
            if k < d and k <= 55:
                down = True

        if up and not down:
            return "bullish"
        if down and not up:
            return "bearish"
        return None

    def build_bullish_triggers(self, ind, prev_ind, kline):
        c = self.get_common_values(ind, prev_ind, kline)
        rsi = c.get("rsi14"); prev_rsi = c.get("prev_rsi14")
        k = c.get("k"); d = c.get("d"); j = c.get("j")
        vol_chg = c.get("vol_chg")

        return {
            # atomic triggers (single-factor)
            "rsi_rebound": (prev_rsi is not None and rsi is not None and prev_rsi < 30 <= rsi),
            "kdj_cross": (c.get("k_prev") is not None and c.get("d_prev") is not None and c.get("k_prev") <= c.get("d_prev") and k is not None and k > d),
            "kdj_extreme": ((j is not None and j < 10) or (k is not None and d is not None and k < 20 and d < 20)),
            "vol_confirm": (vol_chg is not None and vol_chg > self.vol_ratio_threshold),
            "rsi_break_50": (prev_rsi is not None and rsi is not None and prev_rsi <= 50 < rsi),
        }

    def build_bearish_triggers(self, ind, prev_ind, kline):
        c = self.get_common_values(ind, prev_ind, kline)
        rsi = c.get("rsi14"); prev_rsi = c.get("prev_rsi14")
        k = c.get("k"); d = c.get("d"); j = c.get("j")
        vol_chg = c.get("vol_chg")

        return {
            "rsi_fall_from_70": (prev_rsi is not None and rsi is not None and prev_rsi > 70 >= rsi),
            "kdj_dead": (c.get("k_prev") is not None and c.get("d_prev") is not None and c.get("k_prev") >= c.get("d_prev") and k is not None and k < d),
            "kdj_overbought": (j is not None and j > 95),
            "vol_confirm": (vol_chg is not None and vol_chg > self.vol_ratio_threshold),
            "rsi_break_50_down": (prev_rsi is not None and rsi is not None and prev_rsi >= 50 > rsi),
        }

    def build_bullish_patterns(self, ind, prev_ind, kline):
        c = self.get_common_values(ind, prev_ind, kline)
        rsi = c.get("rsi14"); prev_rsi = c.get("prev_rsi14")
        k = c.get("k"); d = c.get("d")
        return {
            # structural patterns get higher weight
            "rsi_bull_div": (c.get("prev_close") is not None and c.get("close") is not None and c.get("close") < c.get("prev_close") and rsi is not None and prev_rsi is not None and rsi > prev_rsi),
            "second_bottom": (prev_rsi is not None and rsi is not None and prev_rsi < rsi < 35 and k is not None and k < 30),
            "rsi_stack": (c.get("rsi6") is not None and rsi is not None and c.get("rsi6") > rsi),
        }

    def build_bearish_patterns(self, ind, prev_ind, kline):
        c = self.get_common_values(ind, prev_ind, kline)
        rsi = c.get("rsi14"); prev_rsi = c.get("prev_rsi14")
        k = c.get("k"); d = c.get("d"); j_prev = c.get("j_prev"); j = c.get("j")
        return {
            "rsi_bear_div": (c.get("prev_close") is not None and c.get("close") is not None and c.get("close") > c.get("prev_close") and rsi is not None and prev_rsi is not None and rsi < prev_rsi),
            "kdj_top_div": (c.get("prev_close") is not None and c.get("close") is not None and c.get("close") > c.get("prev_close") and j_prev is not None and j is not None and j < j_prev),
            "wave_sync_down": (rsi is not None and prev_rsi is not None and rsi < prev_rsi and k is not None and d is not None and k < d),
        }
