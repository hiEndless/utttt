from . import register_plugin
from .base import build_event, last_close, prev_close, CompositeComboBase


def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None


@register_plugin
class BollVolCombo(CompositeComboBase):
    """
    BOLL + VOL + ATR 组合策略（增强版本）
    支持：
    - 上轨突破 + VOL 放大
    - 下轨突破 + VOL 放大
    - 中轨回踩（低量确认）
    - 带宽收缩 + ATR 突破
    - 成交量突刺 / 成交量骤降
    """

    name = "boll_vol_combo"
    version = "3.0"

    required_indicators = ["boll", "vol"]

    bullish_signal = "boll_vol_bullish"
    bearish_signal = "boll_vol_bearish"
    neutral_signal = "boll_vol_neutral"

    # -----------------------------------------------------
    # 核心：构建触发器（bull / bear / neutral）
    # -----------------------------------------------------

    def build_bullish_triggers(self, ind, prev_ind, kline):
        params = self._resolve_params(getattr(self, "_current_interval", ""))
        b = ind.get("boll", {})
        v = ind.get("vol", {})
        atr = v.get("atr")

        upper, lower, mid = b.get("upper_band"), b.get("lower_band"), b.get("middle_band")
        close = last_close(kline)
        prev_c = prev_close(kline)

        vol_now = safe_float(kline[-1][5]) if len(kline) >= 1 else None
        vol_prev = safe_float(kline[-2][5]) if len(kline) >= 2 else None

        if None in (upper, lower, mid, close, prev_c, vol_now, vol_prev, atr):
            return {}

        band_width = (upper - lower) / mid if mid else 0
        vol_ratio = (vol_now / vol_prev) if (vol_prev and vol_now is not None) else 1

        return {

            # --- 强势突破上轨 ---
            "upper_breakout_vol": (
                prev_c <= upper < close and vol_now > vol_prev
            ),

            # --- 中轨回踩 + 量能缩小 ---
            "mid_retest_low_vol": (
                lower < close < mid and prev_c > mid and vol_now < vol_prev
            ),

            # --- 带宽极窄 + ATR 方向突破 ---
            "band_squeeze_atr_up": (
                band_width < params.get("band_squeeze_width_updown", 0.02) and (close - prev_c) > atr
            ),

            # --- 成交量异常放大（多头通常偏强）---
            "vol_spike": vol_ratio > params.get("vol_spike_ratio", 1.5),
        }

    def build_bearish_triggers(self, ind, prev_ind, kline):
        params = self._resolve_params(getattr(self, "_current_interval", ""))
        b = ind.get("boll", {})
        v = ind.get("vol", {})
        atr = v.get("atr")

        upper, lower, mid = b.get("upper_band"), b.get("lower_band"), b.get("middle_band")
        close = last_close(kline)
        prev_c = prev_close(kline)

        vol_now = safe_float(kline[-1][5]) if len(kline) >= 1 else None
        vol_prev = safe_float(kline[-2][5]) if len(kline) >= 2 else None

        if None in (upper, lower, mid, close, prev_c, vol_now, vol_prev, atr):
            return {}

        band_width = (upper - lower) / mid if mid else 0
        vol_ratio = (vol_now / vol_prev) if (vol_prev and vol_now is not None) else 1

        return {

            # --- 强势跌破下轨 ---
            "lower_breakout_vol": (
                prev_c >= lower > close and vol_now > vol_prev
            ),

            # --- 带宽极窄 + ATR 方向破下 ---
            "band_squeeze_atr_down": (
                band_width < params.get("band_squeeze_width_updown", 0.02) and (prev_c - close) > atr
            ),

            # --- 成交量雪崩（下跌前兆）---
            "vol_collapse": vol_ratio < params.get("vol_collapse_ratio", 0.5),
        }

    # -----------------------------
    # 中性模式（不偏多不偏空）
    # -----------------------------
    def build_neutral_triggers(self, ind, prev_ind, kline):
        params = self._resolve_params(getattr(self, "_current_interval", ""))
        b = ind.get("boll", {})
        close = last_close(kline)
        upper, lower, mid = b.get("upper_band"), b.get("lower_band"), b.get("middle_band")
        if None in (upper, lower, mid, close):
            return {}
        band_width = (upper - lower) / mid if mid else 0
        return {
            "near_upper": abs(close - upper) / close < params.get("neutral_near_tol", 0.01),
            "near_lower": abs(close - lower) / close < params.get("neutral_near_tol", 0.01),
            "band_squeeze": band_width < params.get("neutral_band_squeeze", 0.015),
        }

    # -----------------------------
    # base payload
    # -----------------------------
    def base_payload(self, ind, prev_ind, kline):
        b = ind.get("boll", {})
        return {
            "upper": b.get("upper_band"),
            "lower": b.get("lower_band"),
            "mid": b.get("middle_band"),
            "close": last_close(kline),
            "vol": safe_float(kline[-1][5]) if len(kline) >= 1 else None,
        }

    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = super().generate(symbol, kline, ind, prev_ind, interval)
        neutral = {k: v for k, v in (self.build_neutral_triggers(ind, prev_ind, kline) or {}).items() if v}
        if neutral and not res:
            payload = {"strength": len(neutral), "triggers": neutral, "plugin": getattr(self, "name", self.__class__.__name__), "side": "neutral"}
            payload.update(self.base_payload(ind, prev_ind, kline) or {})
            res.append(build_event(symbol, kline, self.neutral_signal, payload, interval))
        return res
