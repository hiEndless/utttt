import uuid
import time
import os
import json
try:
    from event_center.config import cfg
except Exception:
    cfg = None
try:
    import redis
except Exception:
    redis = None


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
        if prev_ind is None:
            try:
                if cfg and redis:
                    client = redis.Redis(host=cfg.redis_host, port=cfg.redis_port, db=cfg.redis_db, password=(cfg.redis_password or None), decode_responses=True)
                    key = f"indicators:prev:binance:{symbol}:{interval}"
                    val = client.get(key)
                    if val:
                        prev_ind = json.loads(val)
            except Exception:
                prev_ind = prev_ind
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
    - Direction 优先策略实现：若 choose_direction() 返回 'bullish'/'bearish'，优先只发该方向事件
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

    _combo_params_cache = None

    @classmethod
    def _load_combo_params(cls):
        if cls._combo_params_cache is not None:
            return cls._combo_params_cache

        def _try_load_yaml(path):
            try:
                import yaml
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            except Exception:
                return None

        base_dir = os.path.dirname(__file__)
        cfg_path = os.path.join(base_dir, "config", "combo_params.yml")
        data = _try_load_yaml(cfg_path) or {}
        cls._combo_params_cache = data
        return data

    def _resolve_params(self, interval: str):
        data = self._load_combo_params() or {}
        g = (data.get("global") or {})
        defaults = g.get("defaults") or {}
        intervals = g.get("intervals") or {}
        params = dict(defaults)
        if interval and interval in intervals:
            params.update(intervals[interval] or {})
        # per-plugin overrides
        plugin_key = getattr(self, "name", self.__class__.__name__)
        p = (data.get("plugins") or {}).get(plugin_key) or {}
        p_def = p.get("defaults") or {}
        p_int = p.get("intervals") or {}
        params.update(p_def)
        if interval and interval in p_int:
            params.update(p_int[interval] or {})
        # fallbacks to class attributes
        params.setdefault("atr_ratio_threshold", getattr(self, "atr_ratio_threshold", 0.004))
        params.setdefault("adx_threshold", getattr(self, "adx_threshold", 15))
        params.setdefault("min_strength", getattr(self, "min_strength", 2))
        params.setdefault("trigger_weight", getattr(self, "trigger_weight", 1))
        params.setdefault("pattern_weight", getattr(self, "pattern_weight", 2))
        return params

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

    def base_filters(self, common, interval=None):
        """
        Returns dict like {"ok": bool, "reason": str?, "trend": bool?}
        - If ok is False, the generator should skip producing signals.
        - trend flag is advisory (used to adjust min_strength).
        """
        close = common.get("close")
        atr = common.get("atr")
        adx = common.get("adx")

        # low-volatility short-circuit: no trend breakouts in very low vol
        params = self._resolve_params(interval or "")
        if close and atr is not None and (atr / close) < params.get("atr_ratio_threshold", self.atr_ratio_threshold):
            return {"ok": False, "reason": "low_volatility"}

        # adx filtering: we don't force skip, but return advisory
        if adx is not None and adx < params.get("adx_threshold", self.adx_threshold):
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

    def compute_strength(self, triggers: dict, patterns: dict, interval: str = ""):
        """权重化 strength，可以 override 或 改为更复杂的权重模型"""
        tcount = len(triggers)
        pcount = len(patterns)
        params = self._resolve_params(interval or "")
        tw = params.get("trigger_weight", self.trigger_weight)
        pw = params.get("pattern_weight", self.pattern_weight)
        return tcount * tw + pcount * pw

    def _filter_items_keep_valid(self, d: dict) -> dict:
        """
        过滤 triggers/patterns 的返回 dict：
        - 只过滤掉 None 和 False（布尔 False），保留 0、''、数字等可能有意义的返回值。
        """
        if not d:
            return {}
        out = {}
        for k, v in d.items():
            if v is None:
                continue
            # explicit False means "not triggered"
            if isinstance(v, bool) and v is False:
                continue
            out[k] = v
        return out

    def generate(self, symbol, kline, ind, prev_ind, interval):
        if prev_ind is None:
            try:
                if cfg and redis:
                    client = redis.Redis(host=cfg.redis_host, port=cfg.redis_port, db=cfg.redis_db, password=(cfg.redis_password or None), decode_responses=True)
                    key = f"indicators:prev:binance:{symbol}:{interval}"
                    val = client.get(key)
                    if val:
                        prev_ind = json.loads(val)
            except Exception:
                prev_ind = prev_ind
        res = []
        common = self.get_common_values(ind, prev_ind, kline)

        # base filters early
        self._current_interval = interval
        filt = self.base_filters(common, interval)
        if not filt.get("ok", True):
            return res  # 跳出，不产生信号

        # get triggers/patterns (subclass) and filter values robustly
        raw_bull_tr = self.build_bullish_triggers(ind, prev_ind, kline) or {}
        raw_bear_tr = self.build_bearish_triggers(ind, prev_ind, kline) or {}
        raw_bull_pt = self.build_bullish_patterns(ind, prev_ind, kline) or {}
        raw_bear_pt = self.build_bearish_patterns(ind, prev_ind, kline) or {}

        bull_tr = self._filter_items_keep_valid(raw_bull_tr)
        bear_tr = self._filter_items_keep_valid(raw_bear_tr)
        bull_pt = self._filter_items_keep_valid(raw_bull_pt)
        bear_pt = self._filter_items_keep_valid(raw_bear_pt)

        # direction preference enforced by subclass choose_direction
        direction = self.choose_direction(ind, prev_ind, kline)
        # direction is either "bullish", "bearish", or None

        # optionally, if not trend (adx low), we may raise threshold: require at least one pattern
        trend_flag = filt.get("trend", True)
        params = self._resolve_params(interval or "")
        min_strength = params.get("min_strength", self.min_strength)
        if not trend_flag:
            # in non-trend, require structure/pattern (avoid false breakouts); escalate threshold
            min_strength = max(min_strength, 3)

        # ---------------------------
        # compute strengths for both sides (patterns-only allowed)
        # ---------------------------
        bullish_strength = self.compute_strength(bull_tr, bull_pt, interval)
        bearish_strength = self.compute_strength(bear_tr, bear_pt, interval)

        # ---------------------------
        # Direction 优先逻辑（你要求）
        # 1) 如果 choose_direction 返回 'bullish'/'bearish'，则优先只考虑该方向（忽略另一方）
        # 2) 否则（choose_direction is None），若两边均满足阈值则产生 neutral
        # ---------------------------
        if direction == "bullish":
            # only allow bullish side
            if bullish_strength >= min_strength:
                payload = {
                    "strength": bullish_strength,
                    "triggers": bull_tr,
                    "patterns": bull_pt,
                    "plugin": getattr(self, "name", self.__class__.__name__),
                    "side": "bullish",
                }
                payload.update(self.base_payload(ind, prev_ind, kline) or {})
                payload.update(common)
                res.append(build_event(symbol, kline, getattr(self, "bullish_signal", "combo_bullish"), payload, interval))
            return res

        if direction == "bearish":
            # only allow bearish side
            if bearish_strength >= min_strength:
                payload = {
                    "strength": bearish_strength,
                    "triggers": bear_tr,
                    "patterns": bear_pt,
                    "plugin": getattr(self, "name", self.__class__.__name__),
                    "side": "bearish",
                }
                payload.update(self.base_payload(ind, prev_ind, kline) or {})
                payload.update(common)
                res.append(build_event(symbol, kline, getattr(self, "bearish_signal", "combo_bearish"), payload, interval))
            return res

        # ---------------------------
        # choose_direction is None -> normal symmetric logic (neutral possible)
        # ---------------------------
        # neutral: both sides meet min_strength
        if bullish_strength >= min_strength and bearish_strength >= min_strength:
            neutral_payload = {
                "strength_bullish": bullish_strength,
                "strength_bearish": bearish_strength,
                "triggers_bullish": bull_tr,
                "patterns_bullish": bull_pt,
                "triggers_bearish": bear_tr,
                "patterns_bearish": bear_pt,
                "plugin": getattr(self, "name", self.__class__.__name__),
                "side": "neutral",
            }
            neutral_payload.update(self.base_payload(ind, prev_ind, kline) or {})
            neutral_payload.update(common)
            res.append(build_event(symbol, kline, "combo_neutral", neutral_payload, interval))
            return res

        # bullish branch (no direction preference)
        if bullish_strength >= min_strength:
            payload = {
                "strength": bullish_strength,
                "triggers": bull_tr,
                "patterns": bull_pt,
                "plugin": getattr(self, "name", self.__class__.__name__),
                "side": "bullish",
            }
            payload.update(self.base_payload(ind, prev_ind, kline) or {})
            payload.update(common)
            res.append(build_event(symbol, kline, getattr(self, "bullish_signal", "combo_bullish"), payload, interval))

        # bearish branch (no direction preference)
        if bearish_strength >= min_strength:
            payload = {
                "strength": bearish_strength,
                "triggers": bear_tr,
                "patterns": bear_pt,
                "plugin": getattr(self, "name", self.__class__.__name__),
                "side": "bearish",
            }
            payload.update(self.base_payload(ind, prev_ind, kline) or {})
            payload.update(common)
            res.append(build_event(symbol, kline, getattr(self, "bearish_signal", "combo_bearish"), payload, interval))

        return res
