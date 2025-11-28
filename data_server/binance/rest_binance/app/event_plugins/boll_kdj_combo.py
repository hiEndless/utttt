from . import register_plugin
from .base import last_close, prev_close, CompositeComboBase


@register_plugin
class KDJBOLLCombo(CompositeComboBase):
    """
    KDJBOLLCombo V4 — 改进版
    - triggers: 原子条件（单因子或简单共振）
    - patterns: 结构性形态（权重更高）
    - 使用 get_common_values/base_filters/base_payload（包含更多字段）
    """

    name = "kdj_boll_combo"
    version = "4.0"
    required_indicators = ["kdj", "boll", "vol"]  # vol 可选，但建议提供
    bullish_signal = "boll_kdj_bullish"
    bearish_signal = "boll_kdj_bearish"

    # 可配置阈值
    band_narrow_threshold = 0.03   # 带宽收窄阈值
    double_tol = 0.02              # double_bottom/top 容忍度（2%）
    near_tol = 0.01                # near lower/upper 相对误差阈值
    vol_ratio_for_confirmation = 1.25

    # 可覆盖基类参数（可按策略调）
    atr_ratio_threshold = 0.0035
    adx_threshold = 18
    vol_ratio_threshold = 1.35
    min_strength = 2
    trigger_weight = 1
    pattern_weight = 2

    def get_common_values(self, ind, prev_ind, kline):
        """
        使用基类 get_common_values 的扩展（增加 boll bands / band_width）
        """
        common = super().get_common_values(ind, prev_ind, kline)
        # boll
        boll = ind.get("boll", {}) or {}
        mid = boll.get("middle_band")
        upper = boll.get("upper_band")
        lower = boll.get("lower_band")
        common.update({"boll_mid": mid, "boll_upper": upper, "boll_lower": lower})

        # band width safe calc
        try:
            if mid and upper is not None and lower is not None and mid != 0:
                common["band_width"] = (upper - lower) / abs(mid)
            else:
                common["band_width"] = 0.0
        except Exception:
            common["band_width"] = 0.0

        # include vol_chg already from base, but make sure present
        # include close/prev_close already included in base
        return common

    def base_payload(self, ind, prev_ind, kline):
        c = self.get_common_values(ind, prev_ind, kline)
        return {
            "k": c.get("k"), "d": c.get("d"), "j": c.get("j"),
            "close": c.get("close"), "prev_close": c.get("prev_close"),
            "boll_mid": c.get("boll_mid"), "boll_upper": c.get("boll_upper"), "boll_lower": c.get("boll_lower"),
            "band_width": c.get("band_width"), "vol_chg": c.get("vol_chg"),
        }

    # ------------------- triggers -------------------
    def build_bullish_triggers(self, ind, prev_ind, kline):
        c = self.get_common_values(ind, prev_ind, kline)
        params = self._resolve_params(getattr(self, "_current_interval", ""))
        k, d, j = c.get("k"), c.get("d"), c.get("j")
        k_prev, d_prev = c.get("k_prev"), c.get("d_prev")
        mid, lower, upper = c.get("boll_mid"), c.get("boll_lower"), c.get("boll_upper")
        close = c.get("close")
        band_width = c.get("band_width", 0.0)
        vol_chg = c.get("vol_chg")

        # 原子 triggers（尽量做简单、可测试的条件）
        return {
            # 低位反转：J 从低位回升并收在中轨上方 (atomic)
            "low_reversal_mid_break": (j is not None and c.get("j_prev") is not None and c.get("j_prev") < params.get("kdj_j_rebound_low", 20) and j >= params.get("kdj_j_rebound_low", 20) and mid is not None and close is not None and close > mid),

            # 金叉且收盘在中轨上方（趋势确认）
            "bull_cross_mid": (k_prev is not None and d_prev is not None and k is not None and d is not None and k_prev < d_prev and k > d and mid is not None and close is not None and close > mid),

            # 下轨支撑（价格接近或触及下轨）
            "near_lower_touch": (lower is not None and close is not None and abs(close - lower) / (close if close else 1) <= params.get("near_tol", self.near_tol)),

            # 双底型（下轨附近金叉）- 需要额外量能或非极窄带宽确认作为加分条件
            "double_bottom_candidate": (
                k_prev is not None and d_prev is not None and k_prev < d_prev and
                k is not None and d is not None and k > d and
                lower is not None and close is not None and
                ((mid is None) or (close < mid)) and
                close <= lower * (1 + params.get("double_tol", self.double_tol))
            ),

            # 带宽极窄时的反转提示（作为 trigger，但通常更适合 pattern）
            "band_narrow": (band_width and band_width < params.get("band_narrow_threshold", self.band_narrow_threshold)),

            # 趋势确认上行：K 上穿 50 且收盘在中轨上方
            "trend_confirm_up": (k_prev is not None and k is not None and k_prev < params.get("kdj_k_mid_break_up", 50) <= k and mid is not None and close is not None and close > mid),
        }

    def build_bearish_triggers(self, ind, prev_ind, kline):
        c = self.get_common_values(ind, prev_ind, kline)
        params = self._resolve_params(getattr(self, "_current_interval", ""))
        k, d, j = c.get("k"), c.get("d"), c.get("j")
        k_prev, d_prev = c.get("k_prev"), c.get("d_prev")
        mid, lower, upper = c.get("boll_mid"), c.get("boll_lower"), c.get("boll_upper")
        close = c.get("close")
        band_width = c.get("band_width", 0.0)
        vol_chg = c.get("vol_chg")

        return {
            "high_reversal_mid_break": (j is not None and c.get("j_prev") is not None and c.get("j_prev") > params.get("kdj_j_reversal_high", 80) and j <= params.get("kdj_j_reversal_high", 80) and mid is not None and close is not None and close < mid),

            "bear_cross_mid": (k_prev is not None and d_prev is not None and k is not None and d is not None and k_prev > d_prev and k < d and mid is not None and close is not None and close < mid),

            "near_upper_touch": (upper is not None and close is not None and abs(upper - close) / (close if close else 1) <= params.get("near_tol", self.near_tol)),

            "double_top_candidate": (
                k_prev is not None and d_prev is not None and k_prev > d_prev and
                k is not None and d is not None and k < d and
                upper is not None and close is not None and
                ((mid is None) or (close > mid)) and
                close >= upper * (1 - params.get("double_tol", self.double_tol))
            ),

            "band_narrow": (band_width and band_width < params.get("band_narrow_threshold", self.band_narrow_threshold)),

            "trend_confirm_down": (k_prev is not None and k is not None and k_prev > params.get("kdj_k_mid_break_down", 50) >= k and mid is not None and close is not None and close < mid),
        }

    # ------------------- patterns（结构性，权重更高） -------------------
    def build_bullish_patterns(self, ind, prev_ind, kline):
        c = self.get_common_values(ind, prev_ind, kline)
        params = self._resolve_params(getattr(self, "_current_interval", ""))
        band_width = c.get("band_width", 0.0)
        lower = c.get("boll_lower")
        close = c.get("close")
        prev_close = c.get("prev_close")
        vol_chg = c.get("vol_chg")

        return {
            # 带宽收窄（表示能量积累） - pattern 权重高
            "band_narrow_pattern": (band_width > 0 and band_width < params.get("band_narrow_threshold", self.band_narrow_threshold)),

            # 下轨附近（结构性支撑）
            "near_lower": (lower is not None and close is not None and abs(close - lower) / (close if close else 1) < params.get("near_tol", self.near_tol)),

            # 中轨回踩后有效反弹（close > prev_close 且回踩接近中轨）
            "mid_retest": (
                prev_close is not None and close is not None and close > prev_close and
                c.get("boll_mid") is not None and
                abs(close - c.get("boll_mid")) / (c.get("boll_mid") if c.get("boll_mid") else 1) < params.get("boll_mid_retest_tol", 0.03)
            ),

            # double bottom 确认（需要量能放大 or 非窄带）
            "double_bottom_confirm": (c.get("vol_chg") is not None and c.get("vol_chg") > params.get("vol_ratio_for_confirmation", self.vol_ratio_for_confirmation)) or (band_width is not None and band_width > params.get("band_narrow_threshold", self.band_narrow_threshold))
        }

    def build_bearish_patterns(self, ind, prev_ind, kline):
        c = self.get_common_values(ind, prev_ind, kline)
        params = self._resolve_params(getattr(self, "_current_interval", ""))
        band_width = c.get("band_width", 0.0)
        upper = c.get("boll_upper")
        close = c.get("close")
        prev_close = c.get("prev_close")

        return {
            "band_narrow_pattern": (band_width > 0 and band_width < params.get("band_narrow_threshold", self.band_narrow_threshold)),
            "near_upper": (upper is not None and close is not None and abs(upper - close) / (close if close else 1) < params.get("near_tol", self.near_tol)),
            "mid_retest_down": (
                prev_close is not None and close is not None and close < prev_close and
                c.get("boll_mid") is not None and
                abs(close - c.get("boll_mid")) / (c.get("boll_mid") if c.get("boll_mid") else 1) < params.get("boll_mid_retest_tol", 0.03)
            ),
            "double_top_confirm": (c.get("vol_chg") is not None and c.get("vol_chg") > params.get("vol_ratio_for_confirmation", self.vol_ratio_for_confirmation)) or (band_width is not None and band_width > params.get("band_narrow_threshold", self.band_narrow_threshold))
        }

