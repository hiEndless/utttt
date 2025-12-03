from . import register_plugin
from .base import build_event, last_close, prev_close, CompositeComboBase


@register_plugin
class EMAMacdCombo(CompositeComboBase):
    """
    EMA + MACD 组合策略（3.0 结构化重构版）

    核心逻辑：
    - EMA 金叉 / 死叉 决定趋势方向
    - MACD 柱、零轴、DIF/DEA 交叉提供动能确认
    - 顶背离 / 底背离用于识别趋势衰竭
    - 成交量、ADX、ATR 提供趋势有效性过滤
    """
    name = "ema_macd_extended_combo"
    version = "3.0"

    required_indicators = ["ema", "macd", "vol"]
    min_adx = 20  # 趋势过滤阈值

    # ---------------------------
    # 统一 Payload
    # ---------------------------
    def base_payload(self, ind, prev_ind, kline):
        e = ind.get("ema", {})
        m = ind.get("macd", {})
        return {
            "ema5": e.get("ema5"),
            "ema12": e.get("ema12"),
            "ema26": e.get("ema26"),
            "dif": m.get("dif"),
            "dea": m.get("dea"),
            "hist": m.get("hist"),
            "close": last_close(kline),
        }

    # =====================================================
    # 多头触发器（趋势增强 / 反转 / 动能增强）
    # =====================================================
    def build_bullish_triggers(self, ind, prev_ind, kline):
        params = self._resolve_params(getattr(self, "_current_interval", ""))
        e, pe = ind.get("ema", {}), prev_ind.get("ema", {}) if prev_ind else {}
        m, pm = ind.get("macd", {}), prev_ind.get("macd", {}) if prev_ind else {}

        ema5, ema12, ema26 = e.get("ema5"), e.get("ema12"), e.get("ema26")
        p5, p12, p26 = pe.get("ema5"), pe.get("ema12"), pe.get("ema26")

        dif, dea, hist = m.get("dif"), m.get("dea"), m.get("hist")
        pdif, pdea, phist = pm.get("dif"), pm.get("dea"), pm.get("hist")

        close = last_close(kline)
        prev_close_value = prev_close(kline)

        atr = ind.get("vol", {}).get("atr")
        adx = ind.get("vol", {}).get("adx")

        # --- 趋势过滤：没有趋势时不做 ----
        low_vol = (close is not None and atr is not None and close != 0 and (atr / close) < params.get("atr_ratio_threshold", 0.004))
        cond_trend = (not low_vol) and (adx is None or adx >= params.get("adx_threshold", getattr(self, "min_adx", 20)))

        return {
            # ===========================
            # 1. EMA 金叉（趋势方向确立）
            # ===========================
            "ema_golden_cross": cond_trend and p12 is not None and p26 is not None and p12 <= p26 < ema12,

            # 2. MACD 柱翻正（动能增强）
            "macd_hist_turn_positive": phist is not None and hist is not None and phist <= 0 < hist,

            # 3. DIF 金叉 DEA（MACD 金叉确认）
            "macd_signal_cross_up": pdif is not None and pdea is not None and pdif <= pdea < dif,

            # ===========================
            # 4. DIF 上穿零轴（趋势加速）
            # ===========================
            "dif_cross_zero_up": pdif is not None and pdif <= 0 < dif,

            # ===========================
            # 5. EMA 三金叉（超级趋势确认）
            # ===========================
            "ema_triple_golden": (
                    p5 is not None and p12 is not None and p26 is not None and
                    p5 <= p12 <= p26 and
                    ema5 is not None and ema12 is not None and ema26 is not None and
                    ema5 > ema12 > ema26
            ),

            # ===========================
            # 6. MACD 连续缩绿（动能反转）
            # ===========================
            "macd_bull_momentum": (
                    phist is not None and hist is not None and pm.get("hist_prev2") is not None and
                    abs(hist) < abs(phist) < abs(pm["hist_prev2"])
            ),

            # ===========================
            # 7. 底背离（空头衰竭 → 反转）
            # DIF 未创新低但价格创新低
            # ===========================
            "bullish_divergence": (
                    prev_close_value is not None and close is not None and
                    dif is not None and pm.get("dif_low") is not None and
                    prev_close_value > close and dif > pm["dif_low"]
            ),
        }

    # =====================================================
    # 空头触发器（趋势反转 / 动能衰弱）
    # =====================================================
    def build_bearish_triggers(self, ind, prev_ind, kline):
        params = self._resolve_params(getattr(self, "_current_interval", ""))
        e, pe = ind.get("ema", {}), prev_ind.get("ema", {}) if prev_ind else {}
        m, pm = ind.get("macd", {}), prev_ind.get("macd", {}) if prev_ind else {}

        ema5, ema12, ema26 = e.get("ema5"), e.get("ema12"), e.get("ema26")
        p5, p12, p26 = pe.get("ema5"), pe.get("ema12"), pe.get("ema26")

        dif, dea, hist = m.get("dif"), m.get("dea"), m.get("hist")
        pdif, pdea, phist = pm.get("dif"), pm.get("dea"), pm.get("hist")

        close = last_close(kline)
        prev_close_value = prev_close(kline)

        atr = ind.get("vol", {}).get("atr")
        adx = ind.get("vol", {}).get("adx")

        low_vol = (close is not None and atr is not None and close != 0 and (atr / close) < params.get("atr_ratio_threshold", 0.004))
        cond_trend = (not low_vol) and (adx is None or adx >= params.get("adx_threshold", getattr(self, "min_adx", 20)))

        return {
            # ===========================
            # 1. EMA 死叉（趋势反转向下）
            # ===========================
            "ema_dead_cross": cond_trend and p12 is not None and p26 is not None and p12 >= p26 > ema12,

            # 2. MACD 柱翻负
            "macd_hist_turn_negative": phist is not None and hist is not None and phist >= 0 > hist,

            # 3. DIF 死叉 DEA
            "macd_signal_cross_down": pdif is not None and pdea is not None and pdif >= pdea > dif,

            # 4. DIF 下穿零轴（空头加速）
            "dif_cross_zero_down": pdif is not None and pdif >= 0 > dif,

            # 5. EMA 三死叉（超级趋势形成）
            "ema_triple_dead": (
                    p5 is not None and p12 is not None and p26 is not None and
                    p5 >= p12 >= p26 and
                    ema5 is not None and ema12 is not None and ema26 is not None and
                    ema5 < ema12 < ema26
            ),

            # 6. MACD 连续缩红（空头动能衰竭）
            "macd_bear_momentum": (
                    phist is not None and hist is not None and pm.get("hist_prev2") is not None and
                    abs(hist) < abs(phist) < abs(pm["hist_prev2"])
            ),

            # ===========================
            # 7. 顶背离（多头衰竭信号）
            # ===========================
            "bearish_divergence": (
                    prev_close_value is not None and close is not None and
                    dif is not None and pm.get("dif_high") is not None and
                    prev_close_value < close and dif < pm["dif_high"]
            ),
        }

    # ----------------------------
    # 中性模式（震荡识别）
    # ----------------------------
    def build_neutral_triggers(self, ind, prev_ind, kline):
        params = self._resolve_params(getattr(self, "_current_interval", ""))
        e = ind.get("ema", {})
        ema12, ema26 = e.get("ema12"), e.get("ema26")
        if ema12 is None or ema26 is None or ema26 == 0:
            return {}
        return {
            "ema_flat": abs(ema12 - ema26) / abs(ema26) < params.get("ema_flat_ratio", 0.002)
        }
