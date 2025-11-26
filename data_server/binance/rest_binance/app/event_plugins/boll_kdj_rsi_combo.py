from . import register_plugin
from .base import build_event, last_close


@register_plugin
class RSIMACDEMACombo:
    name = "triple_rsi_ema_macd"
    version = "1.0"
    required_indicators = ["rsi", "ema", "macd"]

    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []

        # 取指标
        r = ind.get("rsi", {})
        e = ind.get("ema", {})
        m = ind.get("macd", {})

        pr = prev_ind.get("rsi", {}) if prev_ind else {}
        pe = prev_ind.get("ema", {}) if prev_ind else {}
        pm = prev_ind.get("macd", {}) if prev_ind else {}

        # 边界检查
        if (
            r.get("rsi14") is None or pr.get("rsi14") is None or
            e.get("ema12") is None or e.get("ema26") is None or
            pe.get("ema12") is None or pe.get("ema26") is None or
            m.get("dif") is None or m.get("dea") is None or
            pm.get("dif") is None or pm.get("dea") is None
        ):
            return res

        rsi, rsi_prev = r["rsi14"], pr["rsi14"]
        ema12, ema26 = e["ema12"], e["ema26"]
        ema12_prev, ema26_prev = pe["ema12"], pe["ema26"]
        dif, dea = m["dif"], m["dea"]
        dif_prev, dea_prev = pm["dif"], pm["dea"]

        # ---- 多头：三信号共振 ----
        if (
            rsi_prev <= 30 < rsi and  # RSI 反弹
            ema12_prev <= ema26_prev and ema12 > ema26 and  # EMA 金叉
            dif_prev <= dea_prev and dif > dea  # MACD 金叉
        ):
            res.append(build_event(
                symbol, kline, "triple_combo_rsi_ema_macd",
                {
                    "direction": "bullish",
                    "rsi14": rsi,
                    "ema12": ema12,
                    "ema26": ema26,
                    "dif": dif,
                    "dea": dea
                },
                interval
            ))

        # ---- 空头：三信号共振 ----
        if (
            rsi_prev >= 70 > rsi and  # RSI 下跌
            ema12_prev >= ema26_prev and ema12 < ema26 and  # EMA 死叉
            dif_prev >= dea_prev and dif < dea  # MACD 死叉
        ):
            res.append(build_event(
                symbol, kline, "triple_combo_rsi_ema_macd",
                {
                    "direction": "bearish",
                    "rsi14": rsi,
                    "ema12": ema12,
                    "ema26": ema26,
                    "dif": dif,
                    "dea": dea
                },
                interval
            ))

        return res
