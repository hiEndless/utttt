import time
from typing import Any, Dict, List, Optional

from ..io.raw_reader import PERIODS, TYPES
from .horizon_aggregate import (
    aggregate_participant_by_horizon,
    aggregate_price_by_horizon,
    funding_for_horizon,
)
from agent_server.agents.experts.background.market_structure.horizon_schema import HORIZONS
from .interval_analysis import _analyze_period
from .kline_fusion import aggregate_kline_background_by_horizon
from .price_funding_analysis import analyze_funding, analyze_price_trends_from_klines


def _init_horizon_block(horizon: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    """初始化单个 horizon 输出块（用于保持 schema 稳定）。"""
    return {
        "horizon": horizon,
        "holding_window": meta.get("holding_window"),
        "intervals": meta.get("intervals", []),
        "interval_weights": meta.get("weights", {}),
        "participant_structure": {},
        "price_structure": {},
        "funding_context": {},
        "trade_permission": {},
        "confidence": 0.0,
    }


def _derive_trade_permission(horizon: str, block: Dict[str, Any]) -> Dict[str, Any]:
    """输出“允许交易的白名单条件”，用于降低 agent 只否定不放行的倾向。"""
    ps = block.get("participant_structure") or {}
    price_s = block.get("price_structure") or {}
    tension = block.get("market_tension") or {}

    if not ps.get("has_evidence"):
        return {
            "trend_follow_allowed": False,
            "counter_trend_allowed": False,
            "scalp_only": False,
            "position_size_cap": 0.0,
            "notes": "证据不足：不建议在该 horizon 内执行策略。",
        }

    state = ps.get("participant_state")
    risk_profile = ps.get("risk_profile")
    strength = price_s.get("strength")
    tension_level = tension.get("level")

    base_cap = 0.3 if horizon == "short_term" else (0.4 if horizon == "mid_term" else 0.5)
    cap = base_cap

    trend_follow_allowed = False
    counter_trend_allowed = False
    scalp_only = horizon == "short_term"

    if tension_level == "high":
        cap = min(cap, 0.2)
        trend_follow_allowed = False
        counter_trend_allowed = True
        scalp_only = True
        return {
            "trend_follow_allowed": trend_follow_allowed,
            "counter_trend_allowed": counter_trend_allowed,
            "scalp_only": scalp_only,
            "position_size_cap": cap,
            "risk_profile": risk_profile,
            "notes": "高张力区：禁止趋势跟随；仅允许小仓位、短持有、反转/对冲类策略。",
        }

    if state in ("divergent_and_unstable", "unstable", "crowded_but_unstable", "divergent", "mixed"):
        trend_follow_allowed = False
        counter_trend_allowed = True
        scalp_only = True if horizon == "short_term" else (strength != "weak")
        cap = min(cap, 0.3 if horizon == "short_term" else 0.35)
        return {
            "trend_follow_allowed": trend_follow_allowed,
            "counter_trend_allowed": counter_trend_allowed,
            "scalp_only": scalp_only,
            "position_size_cap": cap,
            "risk_profile": risk_profile,
            "notes": "非趋势友好：允许博弈但不建议按趋势追单；以回撤/均值回归/对冲为主。",
        }

    if state == "aligned_and_stable":
        trend_follow_allowed = True
        counter_trend_allowed = strength == "weak"
        scalp_only = False
        cap = min(cap, 0.6 if horizon != "short_term" else 0.4)
        return {
            "trend_follow_allowed": trend_follow_allowed,
            "counter_trend_allowed": counter_trend_allowed,
            "scalp_only": scalp_only,
            "position_size_cap": cap,
            "risk_profile": risk_profile,
            "notes": "趋势友好：可按该 horizon 的方向执行；仍建议控制仓位上限。",
        }

    return {
        "trend_follow_allowed": False,
        "counter_trend_allowed": True,
        "scalp_only": True,
        "position_size_cap": min(cap, 0.25),
        "risk_profile": risk_profile,
        "notes": "默认保护：允许低仓位非趋势策略，避免跨周期信息误用。",
    }


def build_horizon_context(data: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    out = {
        "symbol": symbol,
        "generated_at": int(time.time() * 1000),
        "by_horizon": {},
        "evidence": {},
        "agent_guidance": {
            "verdict_scope": "short_term",
            "avoid_cross_horizon_veto": True,
            "notes": "market_structure 为分层背景信息；各字段多为描述态，不等价于交易行动态信号。裁决时需显式声明当前 verdict 针对的 horizon。",
        },
    }

    ps_interval = {}
    for dtype in TYPES:
        ps_interval[dtype] = {}
        for p in PERIODS:
            ps_interval[dtype][p] = _analyze_period(dtype, data.get(dtype, {}).get(p, []))

    price_interval = analyze_price_trends_from_klines(data.get("klines", {}), PERIODS)
    funding_ctx = analyze_funding(data.get("fundingRate", []))

    out["evidence"]["participant_structure"] = ps_interval
    out["evidence"]["price"] = price_interval
    out["evidence"]["funding"] = funding_ctx

    for hz, meta in HORIZONS.items():
        block = _init_horizon_block(hz, meta)

        block["participant_structure"] = aggregate_participant_by_horizon(ps_interval, meta["intervals"], weights=meta.get("weights"))
        block["price_structure"] = aggregate_price_by_horizon(price_interval, meta["intervals"], weights=meta.get("weights"))
        block["funding_context"] = funding_for_horizon(hz, funding_ctx)

        price_s = block["price_structure"]
        ps = block["participant_structure"]
        tension_level = "low"
        tension_type = "none"
        if (
            price_s.get("strength") == "strong"
            and price_s.get("direction") in ("up", "down")
            and ps.get("participant_state") in ("crowded_but_unstable", "divergent_and_unstable", "unstable")
        ):
            tension_level = "high"
            tension_type = "price_strong_participants_unstable"
        elif price_s.get("strength") in ("strong", "medium") and ps.get("participant_state") in ("divergent", "mixed"):
            tension_level = "medium"
            tension_type = "multi_signal_divergence"

        block["market_tension"] = {"level": tension_level, "type": tension_type}
        block["trade_permission"] = _derive_trade_permission(hz, block)

        block["confidence"] = round(
            (block["participant_structure"].get("confidence", 0) + block["price_structure"].get("consistency", 0)) / 2,
            2,
        )

        out["by_horizon"][hz] = block

    return out


def build_fused_horizons(
    data: Dict[str, Any],
    symbol: str,
    kline_backgrounds: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    base = build_horizon_context(data, symbol)
    horizons: Dict[str, Any] = {}

    for hz, meta in HORIZONS.items():
        block = (base.get("by_horizon") or {}).get(hz) or {}
        ps = block.get("participant_structure") or {}
        price_s = block.get("price_structure") or {}
        tension = block.get("market_tension") or {}

        participant_background = {
            "crowding": "high"
            if "crowded" in _safe_text(ps.get("participant_state"))
            else ("low" if ps.get("has_evidence") else "insufficient_evidence"),
            "dominant_side": ps.get("bias", "neutral"),
            "stability": "fragile"
            if ps.get("stability") == "volatile"
            else ("stable" if ps.get("stability") == "stable" else ps.get("stability", "insufficient_evidence")),
            "participant_state": ps.get("participant_state"),
            "risk_profile": ps.get("risk_profile"),
            "trade_permission": block.get("trade_permission"),
        }

        market_background = aggregate_kline_background_by_horizon(kline_backgrounds or [], meta.get("intervals", []), weights=meta.get("weights"))

        market_background["trend_memory"] = {
            "price_direction": price_s.get("direction", "flat"),
            "price_strength": price_s.get("strength", "weak"),
            "price_consistency": price_s.get("consistency", 0.0),
        }
        market_background["trend_context"] = _derive_trend_context(hz, market_background, price_s, ps, tension)

        conf = round((float(market_background.get("confidence", 0.0)) + float(ps.get("confidence", 0.0))) / 2, 2)

        horizons[hz] = {
            "holding_window": meta.get("holding_window"),
            "market_background": market_background,
            "participant_background": participant_background,
            "confidence": conf,
        }

    return {
        "symbol": symbol,
        "generated_at": base.get("generated_at"),
        "horizons": horizons,
        "agent_guidance": base.get("agent_guidance"),
    }


def _derive_trend_context(
    horizon: str,
    market_background: Dict[str, Any],
    price_structure: Dict[str, Any],
    participant_structure: Dict[str, Any],
    market_tension: Dict[str, Any],
) -> str:
    """基于价格/参与者/结构/张力组合，输出可消费的趋势语境标签。

    说明：
    - 该字段用于“语境分类”，不是交易信号本身。
    - 为了便于上层消费，默认不返回 unknown；当未命中细分分支时返回更宽泛的标签。
    """
    direction = price_structure.get("direction")
    strength = price_structure.get("strength")
    p_state = participant_structure.get("participant_state")
    risk_profile = participant_structure.get("risk_profile")
    mb_struct = _safe_text(market_background.get("structure_state"))
    tension_level = market_tension.get("level")

    if tension_level == "high":
        return "price_strong_participants_unstable"

    if mb_struct.startswith("range_consolidation") or mb_struct.startswith("range_conflict"):
        if direction in ("up", "down") and strength in ("medium", "strong"):
            return "post_trend_consolidation"
        if risk_profile in ("high_volatility_tradeable", "high_risk_breakdown_zone"):
            return "high_volatility_gameable_range"
        return "range_chop"

    mb_struct_l = mb_struct.lower().strip()
    if "break" in mb_struct_l:
        if risk_profile in ("high_risk_breakdown_zone", "high_volatility_tradeable"):
            return "breakdown_high_risk"
        if direction == "down" and strength in ("medium", "strong"):
            return "trend_breakdown_in_progress"
        return "breakdown_watch"

    if strength in ("strong", "medium") and direction in ("up", "down"):
        if p_state in ("crowded_but_unstable", "divergent_and_unstable", "unstable"):
            return "trend_present_but_participants_unstable"
        if p_state == "aligned_and_stable":
            return "trend_continuation_friendly" if strength == "strong" else "trend_continuation_possible"
        if p_state in ("divergent", "mixed"):
            return "trend_present_multi_signal_divergence"
        return "directional_trend_present"

    if strength == "weak" and direction == "flat":
        if p_state in ("divergent", "mixed"):
            return "non_trend_trade_only"
        return "low_signal"

    if horizon == "long_term" and direction in ("up", "down") and strength in ("medium", "strong"):
        return "macro_trend_in_progress"

    if mb_struct_l and mb_struct_l != "unknown":
        return "structural_state_driven"

    if strength in ("strong", "medium"):
        return "momentum_watch"

    return "general_context"


def _safe_text(x: Any) -> str:
    try:
        return str(x or "")
    except Exception:
        return ""
