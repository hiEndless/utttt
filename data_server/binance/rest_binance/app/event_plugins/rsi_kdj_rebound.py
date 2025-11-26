from . import register_plugin
from .base import build_event, last_close


@register_plugin
class RSIKDJRebound:
    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []

        r = ind.get("rsi", {})
        k = ind.get("kdj", {})
        v = ind.get("vol", {})

        pr = prev_ind.get("rsi", {}) if prev_ind else {}
        pk = prev_ind.get("kdj", {}) if prev_ind else {}

        rsi = r.get("rsi14")
        prev_rsi = pr.get("rsi14")

        k_now = k.get("k")
        d_now = k.get("d")
        k_prev = pk.get("k") if pk else None
        d_prev = pk.get("d") if pk else None

        if rsi is None or prev_rsi is None or k_now is None or d_now is None:
            return res

        close = last_close(kline)
        atr = v.get("atr")
        adx = v.get("adx")

        # --- 过滤低波动横盘 ---
        if close and atr and (atr / close) < 0.004:
            return res

        # --- 过滤弱趋势（横盘） ---
        if adx is not None and adx < 20:
            return res

        # =============== 超卖反弹组合逻辑 ===============

        # 1. RSI 从 <30 反上 30（真正反弹）
        rsi_rebound = (prev_rsi < 30 and rsi >= 30)

        # 2. KDJ 金叉（确认反弹动能）
        kdj_cross = False
        if k_prev is not None and d_prev is not None:
            kdj_cross = (k_now > d_now and k_prev <= d_prev)

        # 3. 放宽条件：KDJ J 太低（极超卖）
        j = k.get("j")
        j_extreme = (j is not None and j < 10)  # 比 <20 更严格

        if rsi_rebound and (kdj_cross or j_extreme):
            res.append(build_event(
                symbol, kline,
                "rsi_kdj_rebound_bull",
                {"rsi14": rsi, "k": k_now, "d": d_now, "j": j},
                interval
            ))

        return res
