from . import register_plugin
from .base import last_close, prev_close, CompositeComboBase


@register_plugin
class RSIKDJVOLCombo(CompositeComboBase):
    """
    多维度组合：RSI（反转/背离） + KDJ（交叉/极值）
    统一结构：direction + triggers + patterns
    """

    name = "rsi_kdj_combo"
    version = "3.0"
    required_indicators = ["rsi", "kdj", "vol"]

    bullish_signal = "rsi_kdj_bullish"
    bearish_signal = "rsi_kdj_bearish"

    def build_bullish_triggers(self, ind, prev_ind, kline):
        r = ind["rsi"]
        kdj = ind["kdj"]
        vol = ind["vol"]
        rsi = r.get("rsi14")
        prev_rsi = prev_ind.get("rsi", {}).get("rsi14") if prev_ind else None
        k = kdj.get("k")
        d = kdj.get("d")
        j = kdj.get("j")
        pk = prev_ind.get("kdj", {}) if prev_ind else {}
        k_prev = pk.get("k")
        d_prev = pk.get("d")
        close = last_close(kline)
        price_prev = prev_close(kline)
        vol_chg = None
        try:
            if len(kline) >= 2:
                v1 = float(kline[-1][5])
                v2 = float(kline[-2][5])
                if v2 > 0:
                    vol_chg = v1 / v2
        except Exception:
            vol_chg = None
        return {
            "rsi_rebound": prev_rsi is not None and rsi is not None and prev_rsi < 30 <= rsi,
            "rsi_bull_div": price_prev and close is not None and close < price_prev and rsi is not None and prev_rsi is not None and rsi > prev_rsi,
            "kdj_cross": k_prev is not None and d_prev is not None and k_prev <= d_prev and k is not None and k > d if d is not None else False,
            "kdj_extreme": (j is not None and j < 10) or (k is not None and d is not None and k < 20 and d < 20),
            "second_bottom": prev_rsi is not None and rsi is not None and k is not None and prev_rsi < rsi < 35 and k < 30,
            "vol_confirm": vol_chg is not None and vol_chg > 1.4,
            "rsi_break_50": prev_rsi is not None and rsi is not None and prev_rsi <= 50 < rsi,
            "kdj_break_mid": k_prev is not None and k is not None and k_prev <= 50 < k,
        }

    def build_bearish_triggers(self, ind, prev_ind, kline):
        r = ind["rsi"]
        kdj = ind["kdj"]
        vol = ind["vol"]
        rsi = r.get("rsi14")
        prev_rsi = prev_ind.get("rsi", {}).get("rsi14") if prev_ind else None
        k = kdj.get("k")
        d = kdj.get("d")
        j = kdj.get("j")
        pk = prev_ind.get("kdj", {}) if prev_ind else {}
        k_prev = pk.get("k")
        d_prev = pk.get("d")
        close = last_close(kline)
        price_prev = prev_close(kline)
        vol_chg = None
        try:
            if len(kline) >= 2:
                v1 = float(kline[-1][5])
                v2 = float(kline[-2][5])
                if v2 > 0:
                    vol_chg = v1 / v2
        except Exception:
            vol_chg = None
        return {
            "rsi_fall_from_70": prev_rsi is not None and rsi is not None and prev_rsi > 70 >= rsi,
            "rsi_bear_div": price_prev and close is not None and close > price_prev and rsi is not None and prev_rsi is not None and rsi < prev_rsi,
            "kdj_dead": k_prev is not None and d_prev is not None and k_prev >= d_prev and k is not None and k < d if d is not None else False,
            "kdj_overbought": j is not None and j > 100,
            "kdj_high_dent": k is not None and d is not None and j is not None and k > 80 and d > 80 and j > 80,
            "vol_confirm": vol_chg is not None and vol_chg > 1.4,
            "rsi_break_50_down": prev_rsi is not None and rsi is not None and prev_rsi >= 50 > rsi,
            "kdj_break_mid_down": k_prev is not None and k is not None and k_prev >= 50 > k,
        }

    def build_bullish_patterns(self, ind, prev_ind, kline):
        r = ind["rsi"]
        kdj = ind["kdj"]
        rsi = r.get("rsi14")
        rsi6 = r.get("rsi6")
        prev_rsi = prev_ind.get("rsi", {}).get("rsi14") if prev_ind else None
        k = kdj.get("k")
        d = kdj.get("d")
        return {
            "wave_sync": rsi is not None and prev_rsi is not None and rsi > prev_rsi and k is not None and d is not None and k > d,
            "rsi_stack": rsi6 is not None and rsi is not None and rsi6 > rsi,
        }

    def build_bearish_patterns(self, ind, prev_ind, kline):
        r = ind["rsi"]
        kdj = ind["kdj"]
        rsi = r.get("rsi14")
        prev_rsi = prev_ind.get("rsi", {}).get("rsi14") if prev_ind else None
        k = kdj.get("k")
        d = kdj.get("d")
        j = kdj.get("j")
        pk = prev_ind.get("kdj", {}) if prev_ind else {}
        j_prev = pk.get("j")
        close = last_close(kline)
        price_prev = prev_close(kline)
        return {
            "wave_sync": rsi is not None and prev_rsi is not None and rsi < prev_rsi and k is not None and d is not None and k < d,
            "top_div_kdj": price_prev and close is not None and close > price_prev and j_prev and j is not None and j < j_prev,
        }

    def choose_direction(self, ind, prev_ind, kline):
        r = ind["rsi"]
        kdj = ind["kdj"]
        rsi = r.get("rsi14")
        prev_rsi = prev_ind.get("rsi", {}).get("rsi14") if prev_ind else None
        k = kdj.get("k")
        d = kdj.get("d")
        bull = (rsi is not None and prev_rsi is not None and rsi > prev_rsi) or (k is not None and d is not None and k > d)
        bear = (rsi is not None and prev_rsi is not None and rsi < prev_rsi) or (k is not None and d is not None and k < d)
        if bull and not bear:
            return "bullish"
        if bear and not bull:
            return "bearish"
        return None

    def base_payload(self, ind, prev_ind, kline):
        r = ind["rsi"]
        kdj = ind["kdj"]
        return {"rsi14": r.get("rsi14"), "k": kdj.get("k"), "d": kdj.get("d"), "j": kdj.get("j")}
