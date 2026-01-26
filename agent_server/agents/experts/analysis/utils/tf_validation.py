import redis
import json
from agent_server.config import settings as cfg

KEY_LEVEL_NEAR_PCT = 0.005


def _read_json(client, key: str):
    try:
        val = client.get(key)
        return json.loads(val) if val else {}
    except Exception:
        return {}


def _build_redis_client():
    return redis.Redis(
        host=cfg.redis_host,
        port=cfg.redis_port,
        db=cfg.redis_db,
        password=(cfg.redis_password or None),
        decode_responses=True,
    )


def load_all_indicators(symbol: str, exchange: str, intervals: list[str], client=None) -> dict:
    """
    从 Redis 读取全周期、全指标（当前与上一时刻），结构：
    {
      "1m": {
        "ema": {..., "prev": {...}},
        "macd": {..., "prev": {...}},
        ...
      },
      ...
    }
    """
    client = client or _build_redis_client()
    out = {}
    ex = exchange
    for iv in intervals or []:
        cur_key = f"indicators:{ex}:{symbol}:{iv}"
        prev_key = f"indicators:prev:{ex}:{symbol}:{iv}"
        cur = _read_json(client, cur_key)
        prev = _read_json(client, prev_key)
        merged = {}
        for k, v in (cur or {}).items():
            merged[k] = dict(v or {})
            if isinstance(prev, dict) and k in prev:
                merged[k]["prev"] = prev.get(k)
        out[iv] = merged
    return out


def _safe_num(v):
    try:
        return float(v)
    except Exception:
        return None


def _gt(a, b):
    return a is not None and b is not None and a > b


def _lt(a, b):
    return a is not None and b is not None and a < b


def _nondec(cur, prev):
    return cur is not None and prev is not None and cur >= prev


def _noninc(cur, prev):
    return cur is not None and prev is not None and cur <= prev


def _abs(v):
    return abs(v) if v is not None else None


def _in_range(v, lo, hi):
    return v is not None and lo <= v <= hi


def _trend_alignment(ind, direction: str):
    ema = ind.get("ema") or {}
    prev = ema.get("prev") or {}
    e5 = _safe_num(ema.get("ema5"))
    e20 = _safe_num(ema.get("ema20"))
    e50 = _safe_num(ema.get("ema50"))
    p5 = _safe_num(prev.get("ema5"))
    p20 = _safe_num(prev.get("ema20"))
    # p50 = _safe_num(prev.get("ema50")) # Unused in simplified logic

    if direction == "bullish":
        # 强多头: 5 > 20 > 50 且均线向上
        if _gt(e5, e20) and _gt(e20, e50) and _nondec(e5, p5) and _nondec(e20, p20):
            return "strong_support"
        # 弱多头: 短期均线金叉
        if _gt(e5, e20):
            return "weak_support"
        # 回调: 短期死叉，但长期趋势向上 (20 > 50)
        if not _gt(e5, e20) and _gt(e20, e50):
            return "neutral"
        # 冲突: 完全空头排列或长期趋势未理顺
        return "conflict"

    if direction == "bearish":
        # 强空头: 5 < 20 < 50 且均线向下
        if _lt(e5, e20) and _lt(e20, e50) and _noninc(e5, p5) and _noninc(e20, p20):
            return "strong_support"
        # 弱空头: 短期均线死叉
        if _lt(e5, e20):
            return "weak_support"
        # 反弹: 短期金叉，但长期趋势向下 (20 < 50)
        if not _lt(e5, e20) and _lt(e20, e50):
            return "neutral"
        # 冲突
        return "conflict"
    
    return "neutral"


def _macd_dead_cross(cur_dif, cur_dea, prev_dif, prev_dea):
    return cur_dif is not None and cur_dea is not None and prev_dif is not None and prev_dea is not None and cur_dif < cur_dea and prev_dif >= prev_dea


def _macd_golden_cross(cur_dif, cur_dea, prev_dif, prev_dea):
    return cur_dif is not None and cur_dea is not None and prev_dif is not None and prev_dea is not None and cur_dif > cur_dea and prev_dif <= prev_dea


def _momentum_alignment(ind, direction: str):
    macd = ind.get("macd") or {}
    macd_prev = macd.get("prev") or {}
    rsi = ind.get("rsi") or {}
    kdj = ind.get("kdj") or {}
    m_cur = _safe_num(macd.get("macd"))
    m_prev = _safe_num(macd_prev.get("macd"))
    dif = _safe_num(macd.get("dif"))
    dea = _safe_num(macd.get("dea"))
    pdif = _safe_num(macd_prev.get("dif"))
    pdea = _safe_num(macd_prev.get("dea"))
    r6 = _safe_num(rsi.get("rsi6"))
    r14 = _safe_num(rsi.get("rsi14"))
    j = _safe_num(kdj.get("j"))
    if direction == "bullish":
        if m_cur is not None and m_prev is not None and m_cur > 0 and m_prev > 0 and m_cur > m_prev and _in_range(r14 or r6, 55, 70):
            return "support"
        if m_cur is not None and m_prev is not None and m_cur > 0 and m_cur <= m_prev and _in_range(r14 or r6, 50, 60):
            return "neutral"
        if (r14 is not None and r14 > 75) or (j is not None and j > 100):
            return "exhaustion"
        if _macd_dead_cross(dif, dea, pdif, pdea) or ((r14 is not None and r14 < 40) or (r6 is not None and r6 < 40)):
            return "conflict"
        return "neutral"
    if direction == "bearish":
        if m_cur is not None and m_prev is not None and m_cur < 0 and m_prev < 0 and _abs(m_cur) > _abs(m_prev) and _in_range(r14 or r6, 30, 45):
            return "support"
        if m_cur is not None and m_prev is not None and m_cur < 0 and _abs(m_cur) <= _abs(m_prev) and _in_range(r14 or r6, 40, 50):
            return "neutral"
        if (r14 is not None and r14 < 25) or (j is not None and j < 0):
            return "exhaustion"
        if _macd_golden_cross(dif, dea, pdif, pdea) or ((r14 is not None and r14 > 60) or (r6 is not None and r6 > 60)):
            return "conflict"
        return "neutral"
    return "neutral"


def _structure_alignment(ind, direction: str):
    boll = ind.get("boll") or ind.get("bollinger") or {}
    percent_b = _safe_num(ind.get("percent_b") if isinstance(ind.get("percent_b"), (int, float, str)) else (boll.get("percent_b") if isinstance(boll.get("percent_b"), (int, float, str)) else None))
    if percent_b is not None:
        if direction == "bullish":
            if percent_b >= 0.6:
                return "support"
            if _in_range(percent_b, 0.35, 0.6):
                return "neutral"
            return "conflict"
        if direction == "bearish":
            if percent_b <= 0.4:
                return "support"
            if _in_range(percent_b, 0.4, 0.65):
                return "neutral"
            return "conflict"
    return "neutral"


def _key_level_conflict(ind, direction: str):
    sr = ind.get("support_resistance") or {}
    price = _safe_num(sr.get("price") or ind.get("price"))
    r1 = _safe_num(sr.get("R1"))
    s1 = _safe_num(sr.get("S1"))
    prev = sr.get("prev") or {}
    p_price = _safe_num(prev.get("price") or (ind.get("prev") or {}).get("price"))
    if direction == "bullish":
        if price is not None and r1 is not None and (r1 - price) / price < KEY_LEVEL_NEAR_PCT and r1 > price:
            return "near_resistance"
        if price is not None and r1 is not None and price > r1 and (p_price is None or p_price > r1):
            return "none"
        if price is not None and r1 is not None and p_price is not None and p_price > r1 > price:
            return "breakout_fail"
        if price is not None and s1 is not None and abs(price - s1) / price < KEY_LEVEL_NEAR_PCT:
            return "none"
        return "none"
    if direction == "bearish":
        if price is not None and s1 is not None and (price - s1) / price < KEY_LEVEL_NEAR_PCT and s1 < price:
            return "near_support"
        if price is not None and s1 is not None and price < s1 and (p_price is None or p_price < s1):
            return "none"
        if price is not None and s1 is not None and p_price is not None and p_price < s1 < price:
            return "breakout_fail"
        if price is not None and r1 is not None and abs(price - r1) / price < KEY_LEVEL_NEAR_PCT:
            return "none"
        return "none"
    return "none"


def _reversal_risk(ind, momentum_alignment: str, key_level: str, direction: str):
    atr = ind.get("atr") or {}
    vol = ind.get("volatility") or {}
    atr_cur = _safe_num(atr.get("value") or atr.get("atr"))
    atr_prev = _safe_num((atr.get("prev") or {}).get("value") or (atr.get("prev") or {}).get("atr"))
    vol_cur = _safe_num(vol.get("value") or vol.get("vol"))
    vol_prev = _safe_num((vol.get("prev") or {}).get("value") or (vol.get("prev") or {}).get("vol"))
    spike = (atr_cur is not None and atr_prev is not None and atr_cur > atr_prev) or (vol_cur is not None and vol_prev is not None and vol_cur > vol_prev)
    if momentum_alignment == "exhaustion" and ((direction == "bullish" and key_level == "near_resistance") or (direction == "bearish" and key_level == "near_support")):
        return "high"
    if momentum_alignment == "exhaustion":
        return "medium"
    if spike and key_level != "none":
        return "medium"
    return "low"


def _final_conclusion(trend, momentum, structure, risk, direction: str):
    if trend == "conflict" or momentum == "conflict" or structure == "conflict":
        return "conflict"
    if trend == "strong_support" and momentum == "support" and structure == "support":
        c = "support"
    elif "support" in (trend, momentum, structure):
        c = "partial_support"
    elif trend == "neutral" and momentum == "neutral" and structure == "neutral":
        c = "partial_support"
    else:
        c = "partial_support"
    if risk == "high":
        if c == "support":
            return "partial_support"
        if c == "partial_support":
            return "conflict"
    return c


def compute_tf_validation_for_interval(interval: str, ind: dict, direction: str) -> dict:
    t = _trend_alignment(ind, direction)
    m = _momentum_alignment(ind, direction)
    s = _structure_alignment(ind, direction)
    k = _key_level_conflict(ind, direction)
    if t == "strong_support" and m == "exhaustion":
        m = "neutral"
    r = _reversal_risk(ind, m, k, direction)
    c = _final_conclusion(t, m, s, r, direction)
    return {
        "interval": interval,
        "trend_alignment": t,
        "momentum_alignment": m,
        "structure_alignment": s,
        "key_level_conflict": k,
        "reversal_risk": r,
        "validation_conclusion": c,
    }


def compute_tf_validation_from_indicators(all_indicators: dict, direction: str) -> dict:
    out = {}
    for iv, ind in (all_indicators or {}).items():
        out[iv] = compute_tf_validation_for_interval(iv, ind or {}, direction)
    return out


def compute_tf_validation(
    symbol: str,
    exchange: str,
    direction: str,
    intervals: list[str],
    all_indicators: dict | None = None,
) -> dict:
    inds = all_indicators if all_indicators is not None else load_all_indicators(symbol, exchange, intervals)
    return compute_tf_validation_from_indicators(inds, direction)


if __name__ == "__main__":
    res = compute_tf_validation("BTCUSDT", "binance", "bullish", ["1m", "5m", "15m"])
    print(json.dumps(res, ensure_ascii=False))
