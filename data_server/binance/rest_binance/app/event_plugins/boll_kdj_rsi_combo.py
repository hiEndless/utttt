from . import register_plugin
from .base import build_event, last_close


@register_plugin
class RSIMACDEMACombo:
    name = "triple_rsi_ema_macd"
    version = "2.0"
    required_indicators = ["rsi", "ema", "macd"]

    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []

        # === 取指标 ===
        r = ind.get("rsi", {})
        e = ind.get("ema", {})
        m = ind.get("macd", {})

        pr = prev_ind.get("rsi", {}) if prev_ind else {}
        pe = prev_ind.get("ema", {}) if prev_ind else {}
        pm = prev_ind.get("macd", {}) if prev_ind else {}

        # === 边界检查 ===
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

        close = last_close(kline)

        # ============================================================
        #                ① 强信号：三指标共振（最强）
        # ============================================================

        # ---- 多头三联共振 ----
        if (
            rsi_prev <= 30 < rsi and       # RSI 反弹
            ema12_prev <= ema26_prev and ema12 > ema26 and  # EMA 金叉
            dif_prev <= dea_prev and dif > dea              # MACD 金叉
        ):
            res.append(build_event(
                symbol, kline, "triple_bullish_rsi_ema_macd",
                {"rsi": rsi, "ema12": ema12, "ema26": ema26, "dif": dif, "dea": dea},
                interval
            ))

        # ---- 空头三联共振 ----
        if (
            rsi_prev >= 70 > rsi and
            ema12_prev >= ema26_prev and ema12 < ema26 and
            dif_prev >= dea_prev and dif < dea
        ):
            res.append(build_event(
                symbol, kline, "triple_bearish_rsi_ema_macd",
                {"rsi": rsi, "ema12": ema12, "ema26": ema26, "dif": dif, "dea": dea},
                interval
            ))

        # ============================================================
        #                ② RSI + EMA 组合信号
        # ============================================================

        # RSI 反弹 + EMA 多头趋势
        if rsi_prev <= 30 < rsi and ema12 > ema26:
            res.append(build_event(
                symbol, kline, "rsi_rebound_ema_uptrend",
                {"rsi": rsi, "ema12": ema12, "ema26": ema26},
                interval
            ))

        # RSI 超买回落 + EMA 空头趋势
        if rsi_prev >= 70 > rsi and ema12 < ema26:
            res.append(build_event(
                symbol, kline, "rsi_drop_ema_downtrend",
                {"rsi": rsi, "ema12": ema12, "ema26": ema26},
                interval
            ))

        # ============================================================
        #                ③ RSI + MACD 组合信号
        # ============================================================

        # RSI 反弹 + MACD 金叉，但 EMA 尚未金叉（反转确认提前量）
        if rsi_prev <= 30 < rsi and dif_prev <= dea_prev and dif > dea:
            res.append(build_event(
                symbol, kline, "rsi_rebound_macd_cross",
                {"rsi": rsi, "dif": dif, "dea": dea},
                interval
            ))

        # RSI 回落 + MACD 死叉
        if rsi_prev >= 70 > rsi and dif_prev >= dea_prev and dif < dea:
            res.append(build_event(
                symbol, kline, "rsi_drop_macd_cross",
                {"rsi": rsi, "dif": dif, "dea": dea},
                interval
            ))

        # ============================================================
        #                ④ EMA + MACD 组合信号（趋势向上向下确认）
        # ============================================================

        # 双金叉：EMA 金叉 + MACD 金叉（不看 RSI）
        if ema12_prev <= ema26_prev and ema12 > ema26 and dif_prev <= dea_prev and dif > dea:
            res.append(build_event(
                symbol, kline, "ema_macd_double_bullish",
                {"ema12": ema12, "ema26": ema26, "dif": dif, "dea": dea},
                interval
            ))

        # 双死叉：EMA 死叉 + MACD 死叉
        if ema12_prev >= ema26_prev and ema12 < ema26 and dif_prev >= dea_prev and dif < dea:
            res.append(build_event(
                symbol, kline, "ema_macd_double_bearish",
                {"ema12": ema12, "ema26": ema26, "dif": dif, "dea": dea},
                interval
            ))

        # ============================================================
        #                ⑤ 背离类信号（结构性强信号）
        # ============================================================

        # 价格创新低但 RSI 未创新低 → RSI 底背离
        if prev_ind and close < prev_ind.get("close", close) and rsi > rsi_prev:
            res.append(build_event(
                symbol, kline, "rsi_bull_divergence",
                {"rsi": rsi, "close": close},
                interval
            ))

        # 价格创新高但 RSI 未创新高 → RSI 顶背离
        if prev_ind and close > prev_ind.get("close", close) and rsi < rsi_prev:
            res.append(build_event(
                symbol, kline, "rsi_bear_divergence",
                {"rsi": rsi, "close": close},
                interval
            ))

        # MACD 同理底背离
        if prev_ind and close < prev_ind.get("close", close) and dif > dif_prev:
            res.append(build_event(
                symbol, kline, "macd_bull_divergence",
                {"dif": dif, "close": close},
                interval
            ))

        # MACD 顶背离
        if prev_ind and close > prev_ind.get("close", close) and dif < dif_prev:
            res.append(build_event(
                symbol, kline, "macd_bear_divergence",
                {"dif": dif, "close": close},
                interval
            ))

        return res

