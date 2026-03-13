from __future__ import annotations

"""Deprecated legacy domain module.

This module is kept only for historical compatibility and offline replay reference.
TradeEventWorkflow minimal main path must not import or call this module.
"""

from typing import Any, Dict, List

from services.market_state_engine.src.contracts import MarketStateMSL

from .contracts import ActionIntent, Confidence, SignalVerdict


def resolve_intent(
    *,
    signal: SignalVerdict,
    msl: MarketStateMSL,
    position_context: Dict[str, Any],
) -> ActionIntent:
    """IntentResolver：SignalVerdict + PositionContext + MSL -> ActionIntent。"""

    reasons: List[str] = []

    has_position = bool((position_context or {}).get("has_position") is True)

    if signal.verdict == "reject":
        return ActionIntent(
            intent="decrease" if has_position else "hold",
            direction="none",
            confidence=signal.confidence,
            reasons=["signal_rejected"],
            notes="信号被否定：默认防御性处理。",
        )

    anomalies = set([str(x) for x in list(msl.anomalies or []) if x])
    if "liquidity_vacuum" in anomalies or "orderbook_liquidity_vacuum" in anomalies:
        return ActionIntent(
            intent="hold",
            direction="none",
            confidence=Confidence(level="low", score=min(signal.confidence.score, 0.45)),
            reasons=["liquidity_vacuum"],
            notes="流动性真空：不产生扩张型交易意图。",
        )

    if msl.market_fragility == "high":
        return ActionIntent(
            intent="hold",
            direction="none",
            confidence=Confidence(level="low", score=min(signal.confidence.score, 0.5)),
            reasons=["fragility_high"],
            notes="市场脆弱性高：默认不扩张。",
        )

    if msl.horizon_alignment == "conflict":
        return ActionIntent(
            intent="hold",
            direction="none",
            confidence=Confidence(level="low", score=min(signal.confidence.score, 0.5)),
            reasons=["horizon_conflict"],
            notes="跨周期冲突：默认观望。",
        )

    if signal.verdict == "uncertain":
        if has_position:
            return ActionIntent(
                intent="decrease",
                direction="none",
                confidence=Confidence(level="low", score=min(signal.confidence.score, 0.45)),
                reasons=["signal_uncertain"],
                notes="信号不确定且已有仓位：倾向减仓。",
            )
        return ActionIntent(
            intent="hold",
            direction="none",
            confidence=Confidence(level="low", score=min(signal.confidence.score, 0.45)),
            reasons=["signal_uncertain"],
            notes="信号不确定：默认观望。",
        )

    direction = signal.direction
    if direction not in ("long", "short"):
        return ActionIntent(
            intent="hold",
            direction="none",
            confidence=signal.confidence,
            reasons=["missing_direction"],
            notes="信号成立但缺少方向：默认观望。",
        )

    if msl.direction_bias in ("bullish", "bearish"):
        if (msl.direction_bias == "bullish" and direction == "short") or (msl.direction_bias == "bearish" and direction == "long"):
            return ActionIntent(
                intent="hold",
                direction="none",
                confidence=Confidence(level="low", score=min(signal.confidence.score, 0.5)),
                reasons=["direction_bias_mismatch"],
                notes="方向偏置与信号方向冲突：默认观望。",
            )

    if msl.market_phase in ("distribution", "contraction"):
        return ActionIntent(
            intent="hold",
            direction="none",
            confidence=Confidence(level="low", score=min(signal.confidence.score, 0.5)),
            reasons=[f"market_phase_{msl.market_phase}"],
            notes="市场阶段偏风险：默认不扩张。",
        )

    reasons.append("signal_accepted")
    return ActionIntent(
        intent="increase",
        direction=direction,
        confidence=signal.confidence,
        reasons=reasons,
        notes="意图解析：允许扩张。",
    )
