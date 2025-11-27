from . import register_plugin
from .base import build_event, last_close, prev_close


@register_plugin
class RSIKDJCombo:
    """
    RSI（超卖/反转） + KDJ（金叉/极值）组合
    适用：U 本位、合约、现货、1m~4h
    """
    name = "rsi_kdj_combo"
    version = "2.0"
    required_indicators = ["rsi", "kdj", "vol"]
    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []

        r = ind.get("rsi", {})
        kdj = ind.get("kdj", {})
        vol = ind.get("vol", {})

        pr = prev_ind.get("rsi", {}) if prev_ind else {}
        pk = prev_ind.get("kdj", {}) if prev_ind else {}

        rsi = r.get("rsi14")
        prev_rsi = pr.get("rsi14")

        k = kdj.get("k")
        d = kdj.get("d")
        j = kdj.get("j")
        k_prev = pk.get("k")
        d_prev = pk.get("d")

        if None in [rsi, prev_rsi, k, d]:
            return res

        close = last_close(kline)
        atr = vol.get("atr")
        adx = vol.get("adx")
        vol_chg = None
        try:
            if len(kline) >= 2:
                v_now = float(kline[-1][5])
                v_prev = float(kline[-2][5])
                if v_prev > 0:
                    vol_chg = v_now / v_prev
        except Exception:
            vol_chg = None

        # ====== 波动过滤 ======
        if (close is not None) and (atr is not None) and (atr / close) < 0.004:
            return res

        # ====== 趋势过滤 ======
        if adx is not None and adx < 15:
            return res

        rsi_rebound = (prev_rsi is not None and rsi is not None and prev_rsi < 30 <= rsi)
        rsi_break_50_up = (prev_rsi is not None and rsi is not None and prev_rsi <= 50 < rsi)
        rsi_break_50_down = (prev_rsi is not None and rsi is not None and prev_rsi >= 50 > rsi)

        rsi_super_oversold = (rsi is not None and rsi < 25)
        rsi_super_overbought = (rsi is not None and rsi > 75)

        price_prev_val = prev_close(kline)
        rsi_bull_div = (price_prev_val is not None and close is not None and rsi is not None and prev_rsi is not None and close < price_prev_val and rsi > prev_rsi)
        rsi_bear_div = (price_prev_val is not None and close is not None and rsi is not None and prev_rsi is not None and close > price_prev_val and rsi < prev_rsi)

        kdj_cross = (k_prev is not None and d_prev is not None and k_prev <= d_prev and k is not None and d is not None and k > d)
        kdj_dead = (k_prev is not None and d_prev is not None and k_prev >= d_prev and k is not None and d is not None and k < d)
        kdj_extreme = ((j is not None and j < 10) or (k is not None and d is not None and k < 20 and d < 20))
        kdj_super_overbought = (j is not None and j > 100)
        kdj_double_cross = (kdj_cross and (k_prev is not None and d_prev is not None and k_prev < d_prev))

        second_bottom = (prev_rsi is not None and rsi is not None and k is not None and prev_rsi < rsi < 35 and k < 30)
        volume_confirm = (vol_chg is not None and vol_chg > 1.4)

        # ========== 多头组合（12 种组合之一） ==========
        bullish_conditions = [
            rsi_rebound and kdj_cross,  # ① RSI 反弹 + KDJ 金叉
            rsi_rebound and kdj_extreme,  # ② RSI 反弹 + KDJ 极值区（J<10 或 K/D<20）
            rsi_bull_div and kdj_cross,  # ③ RSI 底背离 + KDJ 金叉
            rsi_bull_div and kdj_extreme,  # ④ RSI 底背离 + KDJ 超卖极值
            second_bottom,  # ⑤ 二次探底（RSI 上升结构 + KDJ 低位）
            (kdj_dead and rsi_rebound and (k is not None and d is not None and k > d)),  # ⑥ 假死叉：死叉后被拉回
            (rsi_break_50_up and (k is not None and d is not None and k > d)),  # ⑦ RSI 上破 50 + KDJ 上行
            ((rsi is not None and 45 <= rsi <= 55) and kdj_cross and kdj_extreme),  # ⑧ RSI 50 附近震荡 + KDJ 超卖反弹
            (rsi_super_oversold and kdj_double_cross),  # ⑨ RSI<30 + KDJ 连续金叉
            (rsi_rebound and kdj_cross and volume_confirm),  # ⑩ 高成交量确认（反弹 + 金叉 + 量能）
            (rsi is not None and rsi > 70 and kdj_super_overbought),  # ⑪ RSI 强势突破 + J>100（强动能）
            (rsi_bull_div and kdj_cross and volume_confirm),  # ⑫ 底背离 + 金叉 + 量能放大
        ]

        if any(bullish_conditions):
            strength_bull = sum(int(c) for c in bullish_conditions)
            res.append(build_event(
                symbol,
                kline,
                "rsi_kdj_combo_bullish",
                {
                    "rsi14": rsi,
                    "k": k,
                    "d": d,
                    "j": j,
                    "strength": strength_bull,
                    "features": {
                        "rsi_rebound": rsi_rebound,
                        "kdj_cross": kdj_cross,
                        "kdj_extreme": kdj_extreme,
                        "rsi_bull_div": rsi_bull_div,
                        "second_bottom": second_bottom,
                        "volume_confirm": volume_confirm,
                    },
                },
                interval,
            ))

        # ========== 空头组合（对称组合） ==========
        bearish_conditions = [
            (prev_rsi is not None and rsi is not None and prev_rsi > 70 >= rsi and kdj_dead),  # A1 RSI 下穿 70 + KDJ 死叉
            (rsi_bear_div and kdj_dead),  # A2 顶背离 + KDJ 死叉
            (rsi_break_50_down and (k is not None and d is not None and k < d)),  # A3 RSI 跌破 50 + KDJ 下行
            (rsi_super_overbought and kdj_dead),  # A4 RSI>75 超买 + 死叉
            (rsi_super_overbought and kdj_super_overbought),  # A5 极端超买（J>100）
        ]

        if any(bearish_conditions):
            strength_bear = sum(int(c) for c in bearish_conditions)
            res.append(build_event(
                symbol,
                kline,
                "rsi_kdj_combo_bearish",
                {"rsi14": rsi, "k": k, "d": d, "j": j, "strength": strength_bear},
                interval,
            ))

        return res
