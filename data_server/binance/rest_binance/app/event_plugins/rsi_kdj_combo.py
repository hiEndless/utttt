from . import register_plugin
from .base import build_event, last_close, prev_close


@register_plugin
class RSIKDJCombo:
    """
    RSI（超卖/反转） + KDJ（金叉/极值）组合
    适用：U 本位、合约、现货、1m~4h
    """
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

        # ====== 组合信号：超卖反弹 ======

        # 1. RSI 真正反弹
        rsi_rebound = (prev_rsi < 30 and rsi >= 30)

        # 2. KDJ 金叉
        kdj_cross = (k_prev is not None and d_prev is not None and k_prev <= d_prev and k > d)

        # 3. KDJ 超卖极端区
        kdj_extreme = (j is not None and j < 10) or (k < 20 and d < 20)

        # 4. 底背离：RSI 上升但价格新低
        price_now = close
        price_prev = prev_close(kline)
        rsi_div_bull = (
            price_now < price_prev and
            rsi > prev_rsi
        ) if price_prev else False

        # 5. 二次探底（RSI 或 KDJ 反弹后再次回踩但不破底）
        second_bottom = (
            prev_rsi < rsi < 35 and
            k < 30
        )

        # 6. 成交量放大确认
        volume_confirm = (vol_chg and vol_chg > 1.3)

        # 触发条件集合 （任意组合）
        if rsi_rebound and (kdj_cross or kdj_extreme or rsi_div_bull or second_bottom):
            strength = sum([
                1 if kdj_cross else 0,
                1 if kdj_extreme else 0,
                1 if rsi_div_bull else 0,
                1 if volume_confirm else 0,
            ])

            res.append(build_event(
                symbol, kline,
                "rsi_kdj_rebound",
                {
                    "rsi14": rsi,
                    "k": k, "d": d, "j": j,
                    "strength": strength,
                    "features": {
                        "kdj_cross": kdj_cross,
                        "kdj_extreme": kdj_extreme,
                        "rsi_div_bull": rsi_div_bull,
                        "second_bottom": second_bottom,
                        "volume_confirm": volume_confirm,
                    }
                },
                interval
            ))

        return res
