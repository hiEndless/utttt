from typing import Any, Dict, List, Optional


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _stability(vol: float) -> str:
    if vol < 0.02:
        return "stable"
    if vol < 0.05:
        return "medium"
    return "volatile"


def _participant_state(
    bias: str,
    stability: str,
    alignment_score: float,
    has_evidence: bool,
) -> str:
    """将描述态的人群信号压缩成可直接使用的“状态标签”（避免下游自行猜测语义）。"""
    if not has_evidence:
        return "unknown"

    crowded = alignment_score >= 0.65 and bias in ("long", "short")
    divergent = alignment_score < 0.55

    if stability == "volatile":
        if crowded:
            return "crowded_but_unstable"
        if divergent:
            return "divergent_and_unstable"
        return "unstable"

    if crowded:
        return "aligned_and_stable"
    if divergent:
        return "divergent"
    return "mixed"


def _risk_profile(participant_state: str) -> str:
    """将 participant_state 映射为“可交易风险画像”（避免 LLM 默认风险厌恶导致全盘否决）。"""
    if participant_state == "unknown":
        return "unknown"

    if participant_state in ("divergent_and_unstable", "unstable"):
        return "high_volatility_tradeable"

    if participant_state == "crowded_but_unstable":
        return "high_risk_breakdown_zone"

    if participant_state == "divergent":
        return "non_trend_trade_only"

    if participant_state == "mixed":
        return "non_trend_trade_only"

    if participant_state == "aligned_and_stable":
        return "trend_tradeable"

    return "unknown"


def aggregate_price_by_horizon(
    price_trends: Dict[str, Any],
    intervals: List[str],
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """将多周期价格趋势压缩为 horizon 级方向与一致性。"""
    trends_map = (price_trends or {}).get("trends", {}) or {}
    w = weights or {}

    up_w = 0.0
    down_w = 0.0
    flat_w = 0.0
    total_w = 0.0

    for p in intervals:
        t = trends_map.get(p)
        if t not in ("up", "down", "flat"):
            continue
        wt = float(w.get(p, 1.0))
        total_w += wt
        if t == "up":
            up_w += wt
        elif t == "down":
            down_w += wt
        else:
            flat_w += wt

    if total_w == 0:
        return {"direction": "flat", "consistency": 0.0, "strength": "unknown"}

    if up_w > down_w and up_w > flat_w:
        direction = "up"
    elif down_w > up_w and down_w > flat_w:
        direction = "down"
    else:
        direction = "flat"

    consistency = round(max(up_w, down_w, flat_w) / total_w, 2)
    if consistency >= 0.8:
        strength = "strong"
    elif consistency >= 0.6:
        strength = "medium"
    else:
        strength = "weak"

    return {"direction": direction, "consistency": consistency, "strength": strength}


def aggregate_participant_by_horizon(
    ps_interval: Dict[str, Any],
    intervals: List[str],
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """将 interval 级参与者结构聚合为 horizon 级摘要。"""
    w = weights or {}
    long_w = 0.0
    short_w = 0.0
    neutral_w = 0.0
    total_w = 0.0

    vol_sum = 0.0
    vol_w_sum = 0.0

    biases: List[str] = []
    vols: List[float] = []

    for dtype, grid in (ps_interval or {}).items():
        if not isinstance(grid, dict):
            continue
        for p in intervals:
            cell = grid.get(p) or {}
            if not isinstance(cell, dict):
                continue
            label = (cell.get("labels") or {}).get("bias")
            if label in ("long", "short", "neutral"):
                biases.append(label)
                wt = float(w.get(p, 1.0))
                total_w += wt
                if label == "long":
                    long_w += wt
                elif label == "short":
                    short_w += wt
                else:
                    neutral_w += wt
            vol = (cell.get("stats") or {}).get("vol_ls_ratio")
            try:
                if vol is not None:
                    fv = float(vol)
                    vols.append(fv)
                    wt = float(w.get(p, 1.0))
                    vol_sum += fv * wt
                    vol_w_sum += wt
            except Exception:
                pass

    long_cnt = biases.count("long")
    short_cnt = biases.count("short")
    neutral_cnt = biases.count("neutral")
    total = len(biases)

    if total == 0 and not vols:
        return {
            "bias": "neutral",
            "bias_kind": "descriptive",
            "alignment_score": 0.0,
            "stability": "unknown",
            "participant_state": "unknown",
            "risk_profile": "unknown",
            "avg_vol": 0.0,
            "confidence": 0.0,
            "has_evidence": False,
            "counts": {"long": 0, "short": 0, "neutral": 0, "total": 0},
        }

    if total_w > 0:
        if long_w > short_w and long_w > neutral_w:
            bias = "long"
        elif short_w > long_w and short_w > neutral_w:
            bias = "short"
        else:
            bias = "neutral"
    elif long_cnt > short_cnt:
        bias = "long"
    elif short_cnt > long_cnt:
        bias = "short"
    else:
        bias = "neutral"

    if total_w > 0:
        alignment_score = round(max(long_w, short_w, neutral_w) / total_w, 2)
    else:
        alignment_score = round(max(long_cnt, short_cnt) / (total or 1), 2)

    avg_vol = (vol_sum / vol_w_sum) if vol_w_sum else (_mean(vols) if vols else 0.0)
    stability = _stability(avg_vol)

    stability_score = 1.0 if stability == "stable" else (0.6 if stability == "medium" else 0.2)
    confidence = round((alignment_score + stability_score) / 2, 2)
    participant_state = _participant_state(bias, stability, alignment_score, True)
    risk_profile = _risk_profile(participant_state)

    return {
        "bias": bias,
        "bias_kind": "descriptive",
        "alignment_score": alignment_score,
        "stability": stability,
        "participant_state": participant_state,
        "risk_profile": risk_profile,
        "avg_vol": round(avg_vol, 6),
        "confidence": confidence,
        "has_evidence": True,
        "counts": {"long": long_cnt, "short": short_cnt, "neutral": neutral_cnt, "total": total},
    }


def funding_for_horizon(horizon: str, funding: Dict[str, Any]) -> Dict[str, Any]:
    """资金费率属于慢变量：短周期仅展示，不参与裁决。"""
    return {
        "bias": funding.get("bias"),
        "stability": funding.get("stability"),
        "trend": funding.get("trend"),
        "use_for_decision": horizon != "short_term",
    }

