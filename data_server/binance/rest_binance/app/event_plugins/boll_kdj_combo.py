from . import register_plugin
from .base import build_event, last_close


@register_plugin
class KDJBOLLCombo:
    name = "kdj_boll_reversal"
    version = "1.0"
    required_indicators = ["kdj", "boll"]

    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []

        kdj = ind.get("kdj", {})
        p_kdj = prev_ind.get("kdj", {}) if prev_ind else {}

        boll = ind.get("boll", {})

        # 边界检查
        if (
            kdj.get("j") is None or p_kdj.get("j") is None or
            boll.get("middle_band") is None
        ):
            return res

        j, j_prev = kdj["j"], p_kdj["j"]
        mid = boll["middle_band"]
        close = last_close(kline)
        if close is None:
            return res

        # ---- 多头反转：KDJ 低位回头 + 收盘站上中轨 ----
        if j_prev < 20 and j >= 20 and close > mid:
            res.append(build_event(
                symbol, kline, "kdj_boll_reversal",
                {
                    "direction": "bullish",
                    "j": j,
                    "boll_mid": mid,
                    "close": close
                },
                interval
            ))

        # ---- 空头反转：KDJ 高位回头 + 收盘跌破中轨 ----
        if j_prev > 80 and j <= 80 and close < mid:
            res.append(build_event(
                symbol, kline, "kdj_boll_reversal",
                {
                    "direction": "bearish",
                    "j": j,
                    "boll_mid": mid,
                    "close": close
                },
                interval
            ))

        return res
