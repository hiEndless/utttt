from . import register_plugin
from .base import build_event


@register_plugin
class EMACrossPlugin:
    name = "ema_cross"
    priority = 10
    level = 2

    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []
        e = ind.get("ema", {})
        p = prev_ind.get("ema", {}) if prev_ind else {}

        if not (e and p):
            return res
        
        ema12, ema26 = e.get("ema12"), e.get("ema26")
        p_ema12, p_ema26 = p.get("ema12"), p.get("ema26")

        if None in (ema12, ema26, p_ema12, p_ema26):
            return res

        # 斜率（用于判断金叉是否有力度）
        slope_now = ema12 - ema26
        slope_prev = p_ema12 - p_ema26

        # 获取价格（用于验证趋势方向）
        close = float(kline[-1][4])

        # bullish cross
        if ema12 > ema26 and p_ema12 <= p_ema26 and slope_now > slope_prev:
            res.append(build_event(
                symbol,
                kline,
                "ema_cross",
                {
                    "direction": "bullish",
                    "ema12": ema12,
                    "ema26": ema26,
                    "slope": round(slope_now - slope_prev, 8)
                },
                interval,
                level=2,
                confidence=0.85
            ))

        # bearish cross
        if ema12 < ema26 and p_ema12 >= p_ema26 and slope_now < slope_prev:
            res.append(build_event(
                symbol,
                kline,
                "ema_cross",
                {
                    "direction": "bearish",
                    "ema12": ema12,
                    "ema26": ema26,
                    "slope": round(slope_prev - slope_now, 8)
                },
                interval,
                level=2,
                confidence=0.85
            ))
        return res
