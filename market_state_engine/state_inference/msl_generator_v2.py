from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from .msl_generator_v1 import build_msl_v1

if TYPE_CHECKING:
    from market_state_engine.engine import MarketStateFeatures
    from market_state_engine.contracts import MarketStateMSL


def _build_summary_v2(state: Dict[str, Any]) -> str:
    trend = str(state.get("trend") or "unknown")
    phase = str(state.get("phase") or "unknown")
    volatility_state = str(state.get("volatility_state") or "unknown")
    liquidity_risk = str(state.get("liquidity_risk") or "unknown")
    crowding = str(state.get("crowding") or "unknown")

    parts: List[str] = []
    if trend in ("bullish", "bearish", "sideways"):
        parts.append(f"trend={trend}/{phase}")
    if volatility_state in ("low", "normal", "high"):
        parts.append(f"vol={volatility_state}")
    if liquidity_risk in ("short_squeeze", "long_squeeze", "neutral"):
        parts.append(f"liq_risk={liquidity_risk}")
    if crowding in ("crowded_long", "crowded_short", "balanced"):
        parts.append(f"crowding={crowding}")
    return "; ".join([p for p in parts if p])


def build_msl_v2(*, features: "MarketStateFeatures", state: Dict[str, Any], plugin_evidence: Dict[str, Any], warnings: List[str]) -> "MarketStateMSL":
    # 复用 v1 映射，确保 schema v2 字段集合一致；仅替换 summary 生成策略。
    msl = build_msl_v1(features=features, state=state, plugin_evidence=plugin_evidence, warnings=warnings)
    summary = _build_summary_v2(state)
    if summary:
        # dataclass frozen=True，需要通过 replace 风格重建
        from dataclasses import replace

        return replace(msl, summary=summary)
    return msl

