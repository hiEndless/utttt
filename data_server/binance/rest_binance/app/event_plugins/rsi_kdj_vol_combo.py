from . import register_plugin
from .base import build_event, last_close, prev_close


@register_plugin
class RSIKDJVOLCombo:
    """
    多维度组合：RSI（反转/背离） + KDJ（交叉/极值）
    统一结构：direction + triggers + patterns
    """

    name = "rsi_kdj_combo"
    version = "3.0"
    required_indicators = ["rsi", "kdj", "vol"]

    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []

        # === 数据抽取 ===
        r = ind["rsi"]
        kdj = ind["kdj"]
        vol = ind["vol"]

        rsi = r.get("rsi14")
        rsi6 = r.get("rsi6")
        prev_rsi = prev_ind.get("rsi", {}).get("rsi14") if prev_ind else None

        k = kdj.get("k")
        d = kdj.get("d")
        j = kdj.get("j")

        pk = prev_ind.get("kdj", {}) if prev_ind else {}
        k_prev = pk.get("k")
        d_prev = pk.get("d")
        j_prev = pk.get("j")

        if None in [rsi, prev_rsi, k, d]:
            return res

        close = last_close(kline)
        price_prev = prev_close(kline)

        # ====== 波动过滤 / 趋势过滤 ======
        atr = vol.get("atr")
        if close and atr and atr / close < 0.004:
            return res

        adx = vol.get("adx")
        if adx and adx < 15:
            return res

        # ===== 成交量变化 =====
        vol_chg = None
        try:
            if len(kline) >= 2:
                v1 = float(kline[-1][5])
                v2 = float(kline[-2][5])
                if v2 > 0:
                    vol_chg = v1 / v2
        except:
            pass

        # ===== 计算所有 TRIGGER ======

        bullish_triggers = {
            "rsi_rebound": prev_rsi < 30 <= rsi,
            "rsi_bull_div": price_prev and close < price_prev and rsi > prev_rsi,
            "kdj_cross": k_prev is not None and d_prev is not None and k_prev <= d_prev < k,
            "kdj_extreme": (j is not None and j < 10) or (k < 20 and d < 20),
            "second_bottom": prev_rsi < rsi < 35 and k < 30,
            "vol_confirm": vol_chg is not None and vol_chg > 1.4,
            "rsi_break_50": prev_rsi <= 50 < rsi,
            "kdj_break_mid": k_prev <= 50 < k,
        }

        bearish_triggers = {
            "rsi_fall_from_70": prev_rsi > 70 >= rsi,
            "rsi_bear_div": price_prev and close > price_prev and rsi < prev_rsi,
            "kdj_dead": k_prev is not None and d_prev is not None and k_prev >= d_prev > k,
            "kdj_overbought": j is not None and j > 100,
            "kdj_high_dent": k > 80 and d > 80 and j > 80,
            "vol_confirm": vol_chg is not None and vol_chg > 1.4,
            "rsi_break_50_down": prev_rsi >= 50 > rsi,
            "kdj_break_mid_down": k_prev >= 50 > k,
        }

        # ===== 高级形态 Pattern =====
        bullish_patterns = {
            "wave_sync": rsi > prev_rsi and k > d,
            "rsi_stack": rsi6 is not None and rsi6 > rsi,
        }

        bearish_patterns = {
            "wave_sync": rsi < prev_rsi and k < d,
            "top_div_kdj": price_prev and close > price_prev and j_prev and j < j_prev,
        }

        # ===== 方向判断 =====
        bullish_direction = rsi > prev_rsi or k > d
        bearish_direction = rsi < prev_rsi or k < d

        # ===== 事件触发 =====
        if bullish_direction:
            active_triggers = {k: v for k, v in bullish_triggers.items() if v}
            active_patterns = {k: v for k, v in bullish_patterns.items() if v}
            if active_triggers:
                strength = len(active_triggers) + len(active_patterns) * 2
                res.append(build_event(
                    symbol, kline,
                    "rsi_kdj_bullish",
                    {
                        "strength": strength,
                        "triggers": active_triggers,
                        "patterns": active_patterns,
                        "rsi14": rsi, "k": k, "d": d, "j": j
                    },
                    interval
                ))

        if bearish_direction:
            active_triggers = {k: v for k, v in bearish_triggers.items() if v}
            active_patterns = {k: v for k, v in bearish_patterns.items() if v}
            if active_triggers:
                strength = len(active_triggers) + len(active_patterns) * 2
                res.append(build_event(
                    symbol, kline,
                    "rsi_kdj_bearish",
                    {
                        "strength": strength,
                        "triggers": active_triggers,
                        "patterns": active_patterns,
                        "rsi14": rsi, "k": k, "d": d, "j": j
                    },
                    interval
                ))

        return res
