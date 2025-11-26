from . import register_plugin
from .base import build_event, last_close


@register_plugin
class KDJBOLLCombo:
    name = "kdj_boll_combo"
    version = "2.0"
    required_indicators = ["kdj", "boll"]

    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []

        kdj = ind.get("kdj", {})
        pk = prev_ind.get("kdj", {}) if prev_ind else {}

        boll = ind.get("boll", {})

        # --- 边界检查 ---
        if (
            kdj.get("j") is None or pk.get("j") is None or
            kdj.get("k") is None or pk.get("k") is None or
            kdj.get("d") is None or pk.get("d") is None or
            boll.get("middle_band") is None or
            boll.get("upper_band") is None or
            boll.get("lower_band") is None
        ):
            return res

        j, j_prev = kdj["j"], pk["j"]
        k, k_prev = kdj["k"], pk["k"]
        d, d_prev = kdj["d"], pk["d"]

        mid = boll["middle_band"]
        upper = boll["upper_band"]
        lower = boll["lower_band"]

        close = last_close(kline)
        if close is None:
            return res

        # ===== 1. 低位反转（你已有） =====
        if j_prev < 20 and j >= 20 and close > mid:
            res.append(build_event(
                symbol, kline, "boll_kdj_low_reversal",
                {"direction": "bullish", "j": j, "close": close, "middle": mid},
                interval
            ))

        # ===== 2. 高位反转（你已有） =====
        if j_prev > 80 and j <= 80 and close < mid:
            res.append(build_event(
                symbol, kline, "boll_kdj_high_reversal",
                {"direction": "bearish", "j": j, "close": close, "middle": mid},
                interval
            ))

        # ===== 3. 金叉 + 中轨支撑（趋势转强） =====
        if k_prev < d_prev and k > d and close > mid:
            res.append(build_event(
                symbol, kline, "kdj_boll_bull_cross",
                {"k": k, "d": d, "close": close, "middle": mid},
                interval
            ))

        # ===== 4. 死叉 + 中轨压制（趋势转弱） =====
        if k_prev > d_prev and k < d and close < mid:
            res.append(build_event(
                symbol, kline, "kdj_boll_bear_cross",
                {"k": k, "d": d, "close": close, "middle": mid},
                interval
            ))

        # ===== 5. J < 10 + 下轨支撑（超卖反弹） =====
        if j < 10 and close >= lower:
            res.append(build_event(
                symbol, kline, "kdj_boll_oversold_rebound",
                {"j": j, "close": close, "lower": lower},
                interval
            ))

        # ===== 6. J > 90 + 上轨压力（超买回调） =====
        if j > 90 and close <= upper:
            res.append(build_event(
                symbol, kline, "kdj_boll_overbought_reject",
                {"j": j, "close": close, "upper": upper},
                interval
            ))

        # ===== 7. 下轨附近金叉（双重反转） =====
        if k_prev < d_prev and k > d and close < mid and close <= lower * 1.02:
            res.append(build_event(
                symbol, kline, "boll_kdj_double_bottom",
                {"k": k, "d": d, "close": close, "lower": lower},
                interval
            ))

        # ===== 8. 上轨附近死叉（双重顶部） =====
        if k_prev > d_prev and k < d and close > mid and close >= upper * 0.98:
            res.append(build_event(
                symbol, kline, "boll_kdj_double_top",
                {"k": k, "d": d, "close": close, "upper": upper},
                interval
            ))

        # ===== 9. KDJ 背离 + 带宽收窄（大级别反转） =====
        band_width = (upper - lower) / mid if mid else 0
        if band_width < 0.03:  # 收窄
            # 价格创新低但KDJ未创新低 → 底背离
            if prev_ind and close < float(prev_ind.get("close", close)) and j > j_prev:
                res.append(build_event(
                    symbol, kline, "boll_kdj_bull_divergence",
                    {"j": j, "band_width": band_width},
                    interval
                ))
            # 价格创新高但KDJ未创新高 → 顶背离
            if prev_ind and close > float(prev_ind.get("close", close)) and j < j_prev:
                res.append(build_event(
                    symbol, kline, "boll_kdj_bear_divergence",
                    {"j": j, "band_width": band_width},
                    interval
                ))

        # ===== 10. 趋势确认：KDJ 上穿50 + 中轨上方 =====
        if k_prev < 50 < k and close > mid:
            res.append(build_event(
                symbol, kline, "boll_kdj_trend_confirm_up",
                {"k": k, "close": close},
                interval
            ))

        # ===== 11. 趋势确认：KDJ 下穿50 + 中轨下方 =====
        if k_prev > 50 > k and close < mid:
            res.append(build_event(
                symbol, kline, "boll_kdj_trend_confirm_down",
                {"k": k, "close": close},
                interval
            ))

        return res

