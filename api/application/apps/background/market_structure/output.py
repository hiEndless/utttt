"""
market_structure.output

用于将 market_structure 下的多个独立结构输出（orderbook / open_interest / behavioral / horizons）
在同一时刻聚合成一个“预决策结构”（pre_decision_structure），方便下游一次性消费。
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, Mapping, Optional, Tuple

if __package__:
    from .behavioral.behavior_output import build_behavior_output
    from .horizon_schema import HORIZONS
    from .horizons.output import build_output as build_horizons_output
    from .open_interest.output import build_output as build_open_interest_output
    from .orderbook.output import build_output as build_orderbook_output
else:
    _d = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.abspath(os.path.join(_d, "..", "..", "..", "..", ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from api.application.apps.background.market_structure.behavioral.behavior_output import build_behavior_output
    from api.application.apps.background.market_structure.horizon_schema import HORIZONS
    from api.application.apps.background.market_structure.horizons.output import build_output as build_horizons_output
    from api.application.apps.background.market_structure.open_interest.output import build_output as build_open_interest_output
    from api.application.apps.background.market_structure.orderbook.output import build_output as build_orderbook_output


SHORT_TERM_MAX_MS = 8 * 60 * 60 * 1000
MID_TERM_MAX_MS = 24 * 60 * 60 * 1000


def _format_duration_ms(duration_ms: int) -> str:
    """将毫秒时长格式化为紧凑的人类可读串（例如 2h15m）。"""
    ms = max(0, int(duration_ms))
    s = ms // 1000
    m = s // 60
    h = m // 60
    d = h // 24
    m = m % 60
    h = h % 24

    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m or not parts:
        parts.append(f"{m}m")
    return "".join(parts)


def _match_horizon_by_duration(duration_ms: int) -> str:
    """根据持仓时长（毫秒）匹配 horizon。"""
    ms = max(0, int(duration_ms))
    if ms <= SHORT_TERM_MAX_MS:
        return "short_term"
    if ms <= MID_TERM_MAX_MS:
        return "mid_term"
    return "long_term"


def _candidate_horizons(primary_horizon: str) -> list[str]:
    """主 horizon 与候选集合的映射：短→短+中；中→中+长；长→长。"""
    hz = str(primary_horizon or "").strip()
    if hz == "short_term":
        return ["short_term", "mid_term"]
    if hz == "mid_term":
        return ["mid_term", "long_term"]
    return ["long_term"]


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _confidence_from_level(level: str) -> Dict[str, Any]:
    lv = str(level or "low")
    if lv not in ("high", "medium", "low"):
        lv = "low"
    score_map = {"high": 0.85, "medium": 0.65, "low": 0.35}
    return {"level": lv, "score": float(score_map.get(lv, 0.35))}


def _confidence_from_score(score: float) -> Dict[str, Any]:
    sc = float(score)
    if sc >= 0.75:
        lv = "high"
    elif sc >= 0.5:
        lv = "medium"
    else:
        lv = "low"
    return {"level": lv, "score": float(round(sc, 4))}


def _interval_to_ms(interval: str) -> int:
    """将 5m/1h/1d 等 interval 解析为毫秒，用于排序与打分。"""
    raw = (interval or "").strip().lower()
    if not raw:
        return 0
    unit = raw[-1]
    num_str = raw[:-1]
    try:
        n = float(num_str)
    except Exception:
        return 0
    if unit == "m":
        return int(n * 60_000)
    if unit == "h":
        return int(n * 3_600_000)
    if unit == "d":
        return int(n * 86_400_000)
    return 0


def _pick_best_oi_cell(open_interest_structure: Mapping[str, Any], horizon: str) -> Tuple[Optional[str], Dict[str, Any]]:
    """从 OI 的 interval 结构中，为指定 horizon 选择一个“代表性”cell。"""
    intervals = list(_safe_dict(HORIZONS.get(horizon)).get("intervals") or [])
    weights = _safe_dict(_safe_dict(HORIZONS.get(horizon)).get("weights") or {})

    best_itv: Optional[str] = None
    best_cell: Dict[str, Any] = {}
    best_score: Tuple[int, int, float, int, int] = (-1, -1, -1.0, -1, -1)

    for itv in intervals:
        cell = _safe_dict(open_interest_structure.get(itv))
        meta = _safe_dict(cell.get("meta"))
        inf = _safe_dict(cell.get("participant_inference"))

        conf = str(inf.get("confidence") or "")
        conf_score = 3 if conf == "high" else (2 if conf == "medium" else (1 if conf == "low" else 0))

        sw = str(meta.get("structural_weight") or "")
        weight_score = 2 if sw == "high" else (1 if sw == "low" else 0)

        hz_weight = float(weights.get(itv) or 0.0)
        latest_ts = int(meta.get("latest_ts") or 0)
        itv_ms = _interval_to_ms(str(itv))

        score = (conf_score, weight_score, hz_weight, latest_ts, itv_ms)
        if score > best_score:
            best_score = score
            best_itv = str(itv)
            best_cell = cell

    return best_itv, best_cell


def _build_micro_liquidity(orderbook_out: Mapping[str, Any], include_snapshot: bool) -> Dict[str, Any]:
    """将 orderbook 输出投影到 micro_liquidity 结构。"""
    snapshot = _safe_dict(orderbook_out.get("orderbook_snapshot"))
    structure_short = _safe_dict(orderbook_out.get("orderbook_structure_short"))
    risk_flags = _safe_dict(orderbook_out.get("orderbook_risk_flags"))

    stability = str(structure_short.get("liquidity_stability") or "unknown")
    if stability not in ("stable", "fragile", "unknown"):
        stability = "unknown"

    conf_score = 0.5
    if stability == "stable":
        conf_score = 0.8
    elif stability == "fragile":
        conf_score = 0.7

    out: Dict[str, Any] = {
        "orderbook_structure": structure_short,
        "risk_flags": risk_flags,
        "meta": {"stability": stability},
        "confidence": _confidence_from_score(conf_score),
    }
    if include_snapshot:
        out["orderbook_snapshot"] = snapshot
    return out


def _build_participant_positioning(open_interest_out: Mapping[str, Any], horizon: str) -> Dict[str, Any]:
    """将 open_interest 输出投影到 participant_positioning 结构。"""
    struct = open_interest_out.get("open_interest_structure") if isinstance(open_interest_out, Mapping) else None
    open_interest_structure = struct if isinstance(struct, Mapping) else {}

    selected_itv: Optional[str] = None
    cell: Dict[str, Any] = {}
    if horizon == "long_term":
        one_day = _safe_dict(open_interest_structure.get("1d"))
        one_day_state = _safe_dict(one_day.get("state"))
        if one_day_state and _safe_float(one_day_state.get("open_interest_value"), default=0.0) > 0.0:
            selected_itv = "1d"
            cell = one_day
        else:
            selected_itv, cell = _pick_best_oi_cell(open_interest_structure, horizon)
    else:
        selected_itv, cell = _pick_best_oi_cell(open_interest_structure, horizon)

    meta = _safe_dict(cell.get("meta"))
    inf = _safe_dict(cell.get("participant_inference"))

    structural_weight = str(meta.get("structural_weight") or "low")
    if structural_weight not in ("high", "low"):
        structural_weight = "low"
    if horizon == "long_term":
        structural_weight = "veto_only"

    confidence_level = str(inf.get("confidence") or "low")
    if confidence_level not in ("high", "medium", "low"):
        confidence_level = "low"

    participant_inference = dict(inf)
    inf_conf_level = str(participant_inference.get("confidence") or "")
    if "confidence" in participant_inference:
        participant_inference.pop("confidence", None)
    if participant_inference:
        participant_inference["confidence"] = _confidence_from_level(inf_conf_level or "low")

    oi_state_raw = _safe_dict(cell.get("state"))
    oi_state = {
        "open_interest": _safe_float(oi_state_raw.get("open_interest"), default=0.0),
        "open_interest_value": _safe_float(oi_state_raw.get("open_interest_value"), default=0.0),
        "oi_to_quote_volume_ratio": _safe_float(oi_state_raw.get("oi_to_quote_volume_ratio"), default=0.0),
    }

    oi_delta_raw = _safe_dict(cell.get("delta"))
    oi_delta = {
        "delta_oi": _safe_float(oi_delta_raw.get("delta_oi"), default=0.0),
        "delta_oi_pct": _safe_float(oi_delta_raw.get("delta_oi_pct"), default=0.0),
    }

    oi_dynamics_raw = _safe_dict(cell.get("dynamics"))
    oi_dynamics = {
        "oi_trend": str(oi_dynamics_raw.get("oi_trend") or "unknown"),
        "oi_velocity": str(oi_dynamics_raw.get("oi_velocity") or "unknown"),
        "oi_acceleration": str(oi_dynamics_raw.get("oi_acceleration") or "unknown"),
    }

    coupling_raw = _safe_dict(cell.get("coupling"))
    coupling: Dict[str, Any] = {"price_trend": str(coupling_raw.get("price_trend") or "unknown"), "taker_bias": str(coupling_raw.get("taker_bias") or "unknown")}
    if coupling_raw.get("agg_trade_mode"):
        coupling["agg_trade_mode"] = str(coupling_raw.get("agg_trade_mode"))

    interpretation_tags = [str(t) for t in list(cell.get("interpretation_tags") or []) if t]
    risk_flags = [str(r) for r in list(cell.get("risk_flags") or []) if r]

    return {
        "oi_state": oi_state,
        "oi_delta": oi_delta,
        "oi_dynamics": oi_dynamics,
        "coupling": coupling,
        "interpretation_tags": interpretation_tags,
        "risk_flags": risk_flags,
        "participant_inference": participant_inference,
        "structural_weight": structural_weight,
        "confidence": _confidence_from_level(confidence_level),
        "meta": {"selected_interval": selected_itv, "selected_latest_ts": int(meta.get("latest_ts") or 0)},
    }


def _build_behavioral_intent(behavior_out: Mapping[str, Any], horizon: str) -> Dict[str, Any]:
    """将行为输出投影到 behavioral_intent 结构。"""
    bs_all = behavior_out.get("behavioral_structure") if isinstance(behavior_out, Mapping) else None
    bs = _safe_dict(_safe_dict(bs_all).get(horizon))

    summary = bs.get("summary")
    summary_dict = _safe_dict(summary)
    status = str(bs.get("status") or "unknown")

    tags: list[str] = []
    dominant_flow = summary_dict.get("dominant_flow")
    market_mode = summary_dict.get("market_mode")
    range_stability = summary_dict.get("range_stability")
    if dominant_flow:
        tags.append(f"dominant_flow_{dominant_flow}")
    if market_mode:
        tags.append(f"market_mode_{market_mode}")
    if range_stability:
        tags.append(f"range_{range_stability}")

    for f in list(summary_dict.get("risk_flags") or []):
        if f:
            tags.append(str(f))
    if status and status not in ("mature", "ok"):
        tags.append(f"status_{status}")

    tags = sorted(set([t for t in tags if t]))

    confidence_level = str(summary_dict.get("flow_confidence") or "low")
    if confidence_level not in ("high", "medium", "low"):
        confidence_level = "low"

    taker_bias: Dict[str, Any] = {}
    if summary_dict:
        taker_bias = {
            "dominant_flow": summary_dict.get("dominant_flow"),
            "flow_confidence": summary_dict.get("flow_confidence"),
            "market_mode": summary_dict.get("market_mode"),
            "range_stability": summary_dict.get("range_stability"),
        }

    return {"taker_bias": taker_bias, "interpretation_tags": tags, "confidence": _confidence_from_level(confidence_level)}


def _build_structural_risks(orderbook_out: Mapping[str, Any], horizons_out: Mapping[str, Any], horizon: str) -> Dict[str, Any]:
    """生成结构风控字段：真空事件来自订单簿；拥挤程度来自 horizons 融合输出。"""
    risk_flags = _safe_dict(orderbook_out.get("orderbook_risk_flags"))
    liquidity_vacuum = bool(risk_flags.get("liquidity_vacuum_event") is True)

    crowding_risk = "unknown"
    fused = _safe_dict(horizons_out.get("fused"))
    hz_block = _safe_dict(_safe_dict(fused.get("horizons")).get(horizon))
    pb = _safe_dict(hz_block.get("participant_background"))
    crowding = str(pb.get("crowding") or "")
    if crowding == "high":
        crowding_risk = "high"
    elif crowding == "low":
        crowding_risk = "low"

    return {"liquidity_vacuum": liquidity_vacuum, "crowding_risk": crowding_risk}


def _build_long_term_structural_context(open_interest_out: Mapping[str, Any], horizons_out: Mapping[str, Any]) -> Dict[str, Any]:
    """构建 long_term 的 veto-only 结构语境：只输出极端/成熟度/拥挤度，不参与细节对比。"""
    pp = _build_participant_positioning(open_interest_out, "long_term")
    oi_delta = _safe_dict(pp.get("oi_delta"))
    oi_dynamics = _safe_dict(pp.get("oi_dynamics"))
    risk_flags = set([str(x) for x in list(pp.get("risk_flags") or []) if x])

    delta_pct = abs(_safe_float(oi_delta.get("delta_oi_pct"), default=0.0))
    velocity = str(oi_dynamics.get("oi_velocity") or "unknown")
    trend = str(oi_dynamics.get("oi_trend") or "unknown")

    leverage_extreme = False
    if delta_pct >= 0.03 and velocity in ("medium", "high"):
        leverage_extreme = True
    if "fragile_leverage_build" in risk_flags or "possible_liquidation_or_unwind" in risk_flags:
        leverage_extreme = True

    if trend == "flat":
        trend_maturity = "early"
    elif velocity == "high" and delta_pct >= 0.03:
        trend_maturity = "late"
    elif velocity in ("medium", "high"):
        trend_maturity = "mid"
    else:
        trend_maturity = "early"

    crowding_percentile = 0.5
    fused = _safe_dict(horizons_out.get("fused"))
    hz_block = _safe_dict(_safe_dict(_safe_dict(fused.get("horizons")).get("long_term")))
    pb = _safe_dict(hz_block.get("participant_background"))
    crowding = str(pb.get("crowding") or "")
    p_state = str(pb.get("participant_state") or "")
    if crowding == "high" or ("crowded" in p_state.lower()):
        crowding_percentile = 0.9
    elif crowding == "low":
        crowding_percentile = 0.2
    if crowding_percentile < 0.3:
        crowding_zone = "low"
    elif crowding_percentile < 0.8:
        crowding_zone = "normal"
    elif crowding_percentile < 0.95:
        crowding_zone = "elevated"
    else:
        crowding_zone = "extreme"

    conf = _safe_dict(pp.get("confidence"))
    score = float(conf.get("score") or 0.35)
    if leverage_extreme and crowding_percentile >= 0.8:
        score = max(score, 0.65)
    if score >= 0.75:
        confidence = _confidence_from_score(score)
    else:
        confidence = _confidence_from_level(str(conf.get("level") or "medium"))

    return {
        "trend_maturity": trend_maturity,
        "leverage_extreme": bool(leverage_extreme),
        "crowding_percentile": {"value": float(round(crowding_percentile, 3)), "zone": crowding_zone},
        "confidence": confidence,
    }


async def build_output(exchange: str, symbol: str, holding_until_ts_ms: int, now_ts_ms: Optional[int] = None) -> Dict[str, Any]:
    """聚合输出。

    参数：
    - holding_until_ts_ms：外部传入的目标时间戳（毫秒）。duration_ms = holding_until_ts_ms - now
    - now_ts_ms：可选；用于离线回放/测试时固定当前时间
    """
    now_ms = int(now_ts_ms if now_ts_ms is not None else time.time() * 1000)
    duration_ms = int(holding_until_ts_ms) - int(now_ms)
    duration_ms = max(0, int(duration_ms))

    holding_horizon = _match_horizon_by_duration(duration_ms)
    candidates = _candidate_horizons(holding_horizon)

    orderbook_task = asyncio.create_task(build_orderbook_output(exchange, symbol))
    oi_task = asyncio.create_task(build_open_interest_output(exchange, symbol))
    beh_task = asyncio.create_task(build_behavior_output(exchange, symbol))
    hz_task = asyncio.create_task(build_horizons_output(exchange, symbol))

    orderbook_out, open_interest_out, behavior_out, horizons_out = await asyncio.gather(
        orderbook_task,
        oi_task,
        beh_task,
        hz_task,
    )

    pre: Dict[str, Any] = {}
    for hz in candidates:
        if hz == "long_term":
            ctx = _build_long_term_structural_context(_safe_dict(open_interest_out), _safe_dict(horizons_out))
            pre[hz] = {
                "structural_context": {k: v for k, v in ctx.items() if k != "confidence"},
                "structural_weight": "veto_only",
                "confidence": _safe_dict(ctx.get("confidence")),
            }
            continue

        cell: Dict[str, Any] = {
            "participant_positioning": _build_participant_positioning(_safe_dict(open_interest_out), hz),
            "behavioral_intent": _build_behavioral_intent(_safe_dict(behavior_out), hz),
            "structural_risks": _build_structural_risks(_safe_dict(orderbook_out), _safe_dict(horizons_out), hz),
        }
        if hz == "short_term":
            cell["micro_liquidity"] = _build_micro_liquidity(_safe_dict(orderbook_out), include_snapshot=True)
        pre[hz] = cell

    return {
        "symbol": symbol,
        "holding_context": {
            "duration_ms": int(duration_ms),
            "duration_human": _format_duration_ms(duration_ms),
            "horizon": holding_horizon,
        },
        "candidate_horizons": candidates,
        "pre_decision_structure": pre,
    }


def main(exchange: str = "binance", symbol: str = "ETHUSDT", holding_until_ts_ms: Optional[int] = None) -> None:
    now_ms = int(time.time() * 1000)
    holding_until_ts_ms = int(holding_until_ts_ms if holding_until_ts_ms is not None else (now_ms + 3 * 60 * 60 * 1000))
    out = asyncio.run(build_output(exchange, symbol, holding_until_ts_ms, now_ts_ms=now_ms))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
