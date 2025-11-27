from . import register_plugin
from .base import last_close, prev_close, CompositeComboBase


@register_plugin
class KDJBOLLCombo(CompositeComboBase):
    name = "kdj_boll_combo"
    version = "2.0"
    required_indicators = ["kdj", "boll"]
    bullish_signal = "boll_kdj_bullish"
    bearish_signal = "boll_kdj_bearish"

    def build_bullish_triggers(self, ind, prev_ind, kline):
        kdj = ind.get("kdj", {})
        pk = prev_ind.get("kdj", {}) if prev_ind else {}
        boll = ind.get("boll", {})
        j, j_prev = kdj.get("j"), pk.get("j")
        k, k_prev = kdj.get("k"), pk.get("k")
        d, d_prev = kdj.get("d"), pk.get("d")
        mid = boll.get("middle_band")
        upper = boll.get("upper_band")
        lower = boll.get("lower_band")
        close = last_close(kline)
        band_width = (upper - lower) / mid if (mid and upper and lower) else 0
        price_prev = prev_close(kline)
        return {
            "low_reversal": j_prev is not None and j is not None and mid is not None and close is not None and j_prev < 20 and j >= 20 and close > mid,
            "bull_cross_mid": k_prev is not None and d_prev is not None and k is not None and d is not None and mid is not None and close is not None and k_prev < d_prev and k > d and close > mid,
            "oversold_rebound": j is not None and lower is not None and close is not None and j < 10 and close >= lower,
            "double_bottom": k_prev is not None and d_prev is not None and k is not None and d is not None and lower is not None and mid is not None and close is not None and k_prev < d_prev and k > d and close < mid and close <= lower * 1.02,
            "bull_div_band_narrow": band_width and band_width < 0.03 and price_prev is not None and close is not None and j is not None and j_prev is not None and close < price_prev and j > j_prev,
            "trend_confirm_up": k_prev is not None and k is not None and mid is not None and close is not None and k_prev < 50 < k and close > mid,
        }

    def build_bearish_triggers(self, ind, prev_ind, kline):
        kdj = ind.get("kdj", {})
        pk = prev_ind.get("kdj", {}) if prev_ind else {}
        boll = ind.get("boll", {})
        j, j_prev = kdj.get("j"), pk.get("j")
        k, k_prev = kdj.get("k"), pk.get("k")
        d, d_prev = kdj.get("d"), pk.get("d")
        mid = boll.get("middle_band")
        upper = boll.get("upper_band")
        lower = boll.get("lower_band")
        close = last_close(kline)
        band_width = (upper - lower) / mid if (mid and upper and lower) else 0
        price_prev = prev_close(kline)
        return {
            "high_reversal": j_prev is not None and j is not None and mid is not None and close is not None and j_prev > 80 and j <= 80 and close < mid,
            "bear_cross_mid": k_prev is not None and d_prev is not None and k is not None and d is not None and mid is not None and close is not None and k_prev > d_prev and k < d and close < mid,
            "overbought_reject": j is not None and upper is not None and close is not None and j > 90 and close <= upper,
            "double_top": k_prev is not None and d_prev is not None and k is not None and d is not None and upper is not None and mid is not None and close is not None and k_prev > d_prev and k < d and close > mid and close >= upper * 0.98,
            "bear_div_band_narrow": band_width and band_width < 0.03 and price_prev is not None and close is not None and j is not None and j_prev is not None and close > price_prev and j < j_prev,
            "trend_confirm_down": k_prev is not None and k is not None and mid is not None and close is not None and k_prev > 50 > k and close < mid,
        }

    def build_bullish_patterns(self, ind, prev_ind, kline):
        boll = ind.get("boll", {})
        upper = boll.get("upper_band")
        lower = boll.get("lower_band")
        mid = boll.get("middle_band")
        close = last_close(kline)
        return {
            "near_lower": lower is not None and close is not None and abs(close - lower) / close < 0.01,
        }

    def build_bearish_patterns(self, ind, prev_ind, kline):
        boll = ind.get("boll", {})
        upper = boll.get("upper_band")
        mid = boll.get("middle_band")
        close = last_close(kline)
        return {
            "near_upper": upper is not None and close is not None and abs(upper - close) / close < 0.01,
        }

    def base_payload(self, ind, prev_ind, kline):
        kdj = ind.get("kdj", {})
        return {"k": kdj.get("k"), "d": kdj.get("d"), "j": kdj.get("j")}

