from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from services.market_state_engine.src.contracts import MarketStateMSL

from services.agent_server_new.domain.contracts import Confidence, SignalVerdict


@dataclass(frozen=True)
class ExpertContext:
    """专家输入上下文：MSL + 关键特征 + 事件本体（避免过度压缩导致信息缺失）。"""

    msl: MarketStateMSL
    key_market_features: Dict[str, Any]
    active_events: List[Dict[str, Any]]
    signal_event: Dict[str, Any]
    position_context: Dict[str, Any]


def evaluate_signal(
    *,
    ctx: ExpertContext,
    signal_direction: str,
) -> SignalVerdict:
    """用 MSL 做主语境，用关键特征做证据补充的规则评估。"""

    direction = "none"
    if str(signal_direction).lower() in ("long", "buy"):
        direction = "long"
    elif str(signal_direction).lower() in ("short", "sell"):
        direction = "short"

    msl = ctx.msl
    ev = (ctx.key_market_features or {}).get("evidence") or {}
    liquidity_vacuum = bool(ev.get("liquidity_vacuum") is True)

    invalidation = []
    if liquidity_vacuum:
        invalidation.append("liquidity_vacuum")
    # 兼容新 MSL 契约：从 liquidity/positioning 子结构读取风险语义。
    if msl.liquidity.liquidity_risk in ("short_squeeze", "long_squeeze") and msl.positioning.crowding in ("crowded_long", "crowded_short"):
        invalidation.append("thin_liquidity_and_high_crowding")
    if msl.horizon_alignment == "conflict":
        invalidation.append("horizon_conflict")
    if "liquidation_cluster" in set([str(x) for x in list(msl.anomalies or [])]):
        invalidation.append("liquidation_cluster")

    if invalidation:
        return SignalVerdict(
            direction="none",
            verdict="reject",
            confidence=Confidence(level="medium", score=0.6),
            invalidation_reasons=invalidation,
            notes="MSL 初筛否定：结构性风险过高。",
        )

    if msl.regime == "transition":
        return SignalVerdict(
            direction=direction,  # type: ignore[arg-type]
            verdict="uncertain",
            confidence=Confidence(level="low", score=0.45),
            invalidation_reasons=[],
            notes="MSL 初筛：处于过渡期，信号不确定。",
        )

    return SignalVerdict(
        direction=direction,  # type: ignore[arg-type]
        verdict="accept",
        confidence=Confidence(level="medium", score=0.65),
        invalidation_reasons=[],
        notes="MSL 初筛通过：可进入风控与动作规划阶段。",
    )
