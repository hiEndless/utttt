import time
from typing import Any, Dict

from .horizon_aggregate import (
    aggregate_participant_by_horizon,
    aggregate_price_by_horizon,
    funding_for_horizon,
)
from .horizon_schema import HORIZONS
from .interval_analysis import _analyze_period
from .price_funding_analysis import analyze_funding, analyze_price_trends_from_klines
from .raw_reader import PERIODS, TYPES


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

    # 高张力：默认只允许小仓位快进快出或反转型（不是“不能交易”，是“不能按趋势交易”）
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

    # 波动/分歧：允许交易但限制风格（避免 LLM 风险厌恶直接否决）
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

    # 结构稳定且一致：允许趋势交易（仓位仍做上限，避免“强行放大”）
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
        "evidence": {},  # interval 级证据，默认仅用于调试
        "agent_guidance": {
            "verdict_scope": "short_term",
            "avoid_cross_horizon_veto": True,
            "notes": "market_structure 为分层背景信息；各字段多为描述态，不等价于交易行动态信号。裁决时需显式声明当前 verdict 针对的 horizon。",
        },
    }

    # ---------- interval-level ----------
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

    # ---------- horizon-level ----------
    for hz, meta in HORIZONS.items():
        block = _init_horizon_block(hz, meta)

        block["participant_structure"] = aggregate_participant_by_horizon(
            ps_interval, meta["intervals"], weights=meta.get("weights")
        )
        block["price_structure"] = aggregate_price_by_horizon(
            price_interval, meta["intervals"], weights=meta.get("weights")
        )
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

        # horizon confidence（可简单，也可后续升级）
        block["confidence"] = round(
            (
                block["participant_structure"].get("confidence", 0)
                + block["price_structure"].get("consistency", 0)
            ) / 2,
            2,
        )

        out["by_horizon"][hz] = block

    return out
