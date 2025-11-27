import uuid
import time


def last_close(kline):
    try:
        return float(kline[-1][4])
    except Exception:
        return None


def last_ts(kline):
    try:
        return int(kline[-1][6])
    except Exception:
        try:
            return int(kline[-1][0])
        except Exception:
            return int(time.time())
    

def build_event(symbol, kline, signal, payload, interval):
    return {
        "event_id": uuid.uuid4().hex,
        "timestamp": last_ts(kline),
        "symbol": symbol,
        "interval": interval,
        "type": "indicator_signal",
        "payload": {"signal": signal, **payload},
    }


def prev_close(kline):
    try:
        return float(kline[-2][4]) if len(kline) >= 2 else None
    except Exception:
        return None


class EventPlugin:
    def generate(self, symbol, kline, ind, prev_ind, interval):
        return []

    def supports(self, symbol, interval, kline, ind):
        try:
            # interval filter
            if hasattr(self, "supported_intervals"):
                si = getattr(self, "supported_intervals") or []
                if si and interval not in si:
                    return False

            # required indicators presence
            req = getattr(self, "required_indicators", None)
            if isinstance(req, (list, tuple)):
                for key in req:
                    if key not in ind:
                        return False

            # generic volatility gating
            vol = ind.get("vol", {})
            adx = vol.get("adx")
            atr = vol.get("atr")
            close = last_close(kline)

            min_adx = getattr(self, "min_adx", None)
            if min_adx is not None:
                if adx is None or adx < min_adx:
                    return False

            min_atr_ratio = getattr(self, "min_atr_ratio", None)
            if min_atr_ratio is not None:
                if close is None or atr is None:
                    return False
                if close == 0:
                    return False
                if (atr / close) < min_atr_ratio:
                    return False

            return True
        except Exception:
            return True


# CompositeComboBase v4 — 可复用基类
class CompositeComboBase(EventPlugin):
    """
    CompositeComboBase V4
    - 统一数据抽取：get_common_values
    - 通用过滤：base_filters (ATR/ADX/min_strength)
    - 权重化 strength：triggers (weight 1), patterns (weight 2) by default
    - 可重写：build_bullish_triggers/build_bearish_triggers/build_bullish_patterns/build_bearish_patterns/choose_direction/base_payload
    """

    # default signal names
    bullish_signal = "combo_bullish"
    bearish_signal = "combo_bearish"

    # config (可被子类覆盖)
    min_strength = 2                # 最小触发 strength（低于则不发事件）
    atr_ratio_threshold = 0.004     # atr/price below -> treat as too low vol (可调整)
    adx_threshold = 15              # adx below -> treat as non-trend (可调整)
    vol_ratio_threshold = 1.4       # 成交量放大阈值
    trigger_weight = 1
    pattern_weight = 2

    def get_common_values(self, ind, prev_ind, kline):
        """统一提取常用值，避免重复计算。返回 dict。"""
        out = {}
        # RSI
        r = ind.get("rsi", {}) or {}
        pr = prev_ind.get("rsi", {}) if prev_ind else {}
        out["rsi14"] = r.get("rsi14")
        out["rsi6"] = r.get("rsi6")
        out["prev_rsi14"] = pr.get("rsi14") if pr else None

        # KDJ
        kdj = ind.get("kdj", {}) or {}
        pk = prev_ind.get("kdj", {}) if prev_ind else {}
        out["k"] = kdj.get("k")
        out["d"] = kdj.get("d")
        out["j"] = kdj.get("j")
        out["k_prev"] = pk.get("k")
        out["d_prev"] = pk.get("d")
        out["j_prev"] = pk.get("j")

        # VOL/ATR/ADX
        vol = ind.get("vol", {}) or {}
        out["atr"] = vol.get("atr")
        out["adx"] = vol.get("adx")
        # compute vol ratio safely
        out["vol_chg"] = None
        try:
            if len(kline) >= 2:
                v_now = float(kline[-1][5])
                v_prev = float(kline[-2][5])
                if v_prev > 0:
                    out["vol_chg"] = v_now / v_prev
        except Exception:
            out["vol_chg"] = None

        # price
        out["close"] = last_close(kline)
        out["prev_close"] = prev_close(kline)

        return out

    def base_filters(self, common):
        """
        Returns False if event generation should be skipped due to market conditions:
        - too low volatility (atr/price < threshold)
        - non-trend (adx < threshold) -> we still allow pattern signals (configurable)
        """
        close = common.get("close")
        atr = common.get("atr")
        adx = common.get("adx")

        # low-volatility short-circuit: no trend breakouts in very low vol
        if close and atr is not None and (atr / close) < self.atr_ratio_threshold:
            return {"ok": False, "reason": "low_volatility"}

        # adx filtering: we don't force skip, but return advisory
        if adx is not None and adx < self.adx_threshold:
            return {"ok": True, "trend": False}
        return {"ok": True, "trend": True}

    # 子类实现这些接口以提供 triggers / patterns / payload / direction
    def build_bullish_triggers(self, ind, prev_ind, kline):
        return {}

    def build_bearish_triggers(self, ind, prev_ind, kline):
        return {}

    def build_bullish_patterns(self, ind, prev_ind, kline):
        return {}

    def build_bearish_patterns(self, ind, prev_ind, kline):
        return {}

    def choose_direction(self, ind, prev_ind, kline):
        """可被子类覆盖：返回 'bullish' / 'bearish' / None（两者都允许）"""
        return None

    def base_payload(self, ind, prev_ind, kline):
        """子类可覆盖以加基本字段"""
        return {}

    def compute_strength(self, triggers: dict, patterns: dict):
        """权重化 strength，可以 override 或 改为更复杂的权重模型"""
        tcount = len(triggers)
        pcount = len(patterns)
        return tcount * self.trigger_weight + pcount * self.pattern_weight

    def generate(self, symbol, kline, ind, prev_ind, interval):
        res = []
        common = self.get_common_values(ind, prev_ind, kline)

        # base filters early
        filt = self.base_filters(common)
        if not filt.get("ok", True):
            return res  # 跳出，不产生信号

        # get triggers/patterns (subclass)
        bull_tr = {k: v for k, v in (self.build_bullish_triggers(ind, prev_ind, kline) or {}).items() if v}
        bear_tr = {k: v for k, v in (self.build_bearish_triggers(ind, prev_ind, kline) or {}).items() if v}
        bull_pt = {k: v for k, v in (self.build_bullish_patterns(ind, prev_ind, kline) or {}).items() if v}
        bear_pt = {k: v for k, v in (self.build_bearish_patterns(ind, prev_ind, kline) or {}).items() if v}

        # direction preference enforced by subclass choose_direction
        direction = self.choose_direction(ind, prev_ind, kline)

        # optionally, if not trend (adx low), we may lower sensitivity: require at least one pattern
        trend_flag = filt.get("trend", True)
        min_strength = self.min_strength
        if not trend_flag:
            # in non-trend, require structure/pattern (avoid false breakouts); escalate threshold
            min_strength = max(min_strength, 3)

        # bullish branch
        if direction in (None, "bullish") and bull_tr:
            strength = self.compute_strength(bull_tr, bull_pt)
            if strength >= min_strength:
                payload = {"strength": strength, "triggers": bull_tr, "patterns": bull_pt}
                payload.update(self.base_payload(ind, prev_ind, kline) or {})
                payload.update(common)  # include common useful fields
                res.append(build_event(symbol, kline, getattr(self, "bullish_signal", "combo_bullish"), payload, interval))

        # bearish branch
        if direction in (None, "bearish") and bear_tr:
            strength = self.compute_strength(bear_tr, bear_pt)
            if strength >= min_strength:
                payload = {"strength": strength, "triggers": bear_tr, "patterns": bear_pt}
                payload.update(self.base_payload(ind, prev_ind, kline) or {})
                payload.update(common)
                res.append(build_event(symbol, kline, getattr(self, "bearish_signal", "combo_bearish"), payload, interval))

        return res

