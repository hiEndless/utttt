from typing import Dict, Literal, Optional, Any
from agent_server.config import settings
from agent_server.agent_context.utils.market_context_utils import adjust_risk_by_market_context

PositionDirection = Literal["long", "short", "flat"]


def is_mainstream_symbol(symbol: str) -> bool:
    """识别主流币，用于调整人群结构分析阈值"""
    mainstream_coins = ['BTC', 'ETH', 'BNB', 'XRP', 'SOL']
    return any(coin in symbol.upper() for coin in mainstream_coins)


def opposite(direction: str) -> Optional[str]:
    if direction == "long":
        return "short"
    if direction == "short":
        return "long"
    return None


def build_crowd_interpretation(
        market_snapshot: Dict[str, Any],
        position_direction: str,  # "long", "short", "flat"
) -> Dict[str, Any]:
    """
    Deterministically build crowd interpretation based on:
    - crowd_state (must be present in market_snapshot)
    - market_state (short_term only)
    - current position direction

    This function:
    - DOES NOT judge signal validity
    - DOES NOT recommend actions
    - ONLY encodes relationship & risk semantics
    """
    # Defensive copy to avoid modifying the input context
    # But we return ONLY the interpretation block, not the full context
    
    # Normalize position direction
    pos_dir: PositionDirection = "flat"
    if position_direction.lower() in ["long", "bullish"]:
        pos_dir = "long"
    elif position_direction.lower() in ["short", "bearish"]:
        pos_dir = "short"

    # No position → no interpretation
    if pos_dir == "flat":
        return {
            "position_direction": "flat",
            "note": "no active position, interpretation skipped"
        }

    crowd_state = market_snapshot.get("crowd_state", {})
    # Support accessing crowd_state directly or nested in market_state
    if not crowd_state and "market_state" in market_snapshot:
         crowd_state = market_snapshot["market_state"].get("crowd_state", {})

    market_state = market_snapshot.get("market_state", {})
    short_term = market_state.get("short_term", {})

    crowd_bias = crowd_state.get("bias", "neutral")
    crowding_level = crowd_state.get("crowding_level", "low")
    fragility = crowd_state.get("fragility", "low")
    funding_pressure = crowd_state.get("funding_pressure", "none")

    short_term_direction = short_term.get("direction", "neutral")

    crowd_trend = market_snapshot.get("crowd_trend_analysis") or {}
    thresholds = market_snapshot.get("crowd_thresholds") or settings.crowd_thresholds
    
    # 获取基础阈值
    extreme_zscore_threshold = float(thresholds.get("extreme_zscore", 2.0))
    building_zscore_threshold = float(thresholds.get("building_zscore", 1.5))
    building_delta_threshold = float(thresholds.get("building_delta", 0.01))
    fragility_requires_crowding = bool(thresholds.get("fragility_requires_crowding", True))
    
    # 获取symbol用于主流币判断
    symbol = market_snapshot.get("symbol", "")
    market_state = market_snapshot.get("market_state", {})
    
    # 市场环境感知调整
    market_adjustments = adjust_risk_by_market_context(market_state)
    crowd_risk_multiplier = market_adjustments["crowd_risk_multiplier"]
    zscore_relaxation = market_adjustments["zscore_relaxation"]
    
    # 主流币阈值调整：提高阈值以避免正常多头倾向被误判为拥挤风险
    if is_mainstream_symbol(symbol):
        mainstream_adjustment = float(thresholds.get("mainstream_bias_adjustment", 0.5))
        extreme_zscore_threshold += mainstream_adjustment  # 提高极端拥挤阈值 (2.0 -> 2.5)
        building_zscore_threshold += mainstream_adjustment * 0.6  # 适度提高建设期阈值 (1.5 -> 1.8)
        building_delta_threshold += mainstream_adjustment * 0.05  # 适度提高delta阈值
    
    # 应用市场环境调整
    extreme_zscore_threshold += zscore_relaxation
    building_zscore_threshold += zscore_relaxation * 0.7
    building_delta_threshold += abs(zscore_relaxation) * 0.01

    def _max_abs_zscore(periods: list[str]) -> float:
        metrics = [
            "account_long_ratio",
            "taker_buy_sell_ratio",
            "top_position_ratio",
            "top_account_ratio",
            "funding_rate",
        ]
        max_abs = 0.0
        for m in metrics:
            obj = crowd_trend.get(m) or {}
            z = obj.get("zscore") or {}
            for p in periods:
                try:
                    val = float(z.get(p, 0.0))
                except Exception:
                    val = 0.0
                if abs(val) > max_abs:
                    max_abs = abs(val)
        return max_abs

    def _has_building_crowding(periods: list[str]) -> bool:
        metrics = [
            "account_long_ratio",
            "taker_buy_sell_ratio",
            "top_position_ratio",
            "top_account_ratio",
        ]
        for m in metrics:
            obj = crowd_trend.get(m) or {}
            z = obj.get("zscore") or {}
            d = obj.get("delta") or {}
            for p in periods:
                try:
                    zval = float(z.get(p, 0.0))
                    dval = float(d.get(p, 0.0))
                except Exception:
                    continue
                if abs(zval) >= building_zscore_threshold and abs(dval) >= building_delta_threshold:
                    return True
        return False

    crowd_extreme = _max_abs_zscore(["15m", "30m", "1h", "4h"]) >= extreme_zscore_threshold
    crowd_building = _has_building_crowding(["15m", "30m", "1h", "4h"])

    # -------- Rule Group 1: Direction Relationship --------
    relationship = "neutral"
    if crowd_bias == pos_dir:
        relationship = "same"
    elif crowd_bias == opposite(pos_dir):
        relationship = "opposite"

    # -------- Rule Group 2: Base Implication --------
    implication = "neutral"
    if relationship == "same":
        if crowding_level == "high" and (crowd_extreme or crowd_building):
            implication = "headwind"
        elif fragility == "high":
            if not fragility_requires_crowding or crowding_level in ["medium", "high"]:
                implication = "headwind"
    elif relationship == "opposite":
        if crowding_level == "high" and (crowd_extreme or crowd_building):
            implication = "tailwind"

    # -------- Rule Group 3: Stability (Crowding) --------
    stability = "stable"
    if crowding_level == "high":
        stability = "unstable" if (crowd_extreme or crowd_building) else "stable"

    # -------- Rule Group 4: Non-linear Risk (Fragility) --------
    nonlinear_risk = "normal"
    if fragility == "high":
        nonlinear_risk = "elevated"

    # -------- Rule Group 5: Execution / Price Confirmation --------
    execution_confirmation = "irrelevant"
    if relationship == "opposite":
        if short_term_direction == pos_dir:
            execution_confirmation = "confirmed"
        else:
            execution_confirmation = "unconfirmed"

    # -------- Risk Tags Aggregation --------
    risk_tags = []

    if stability == "unstable":
        risk_tags.append("crowding_instability")

    if nonlinear_risk == "elevated":
        risk_tags.append("fragility_non_linear_risk")

    if funding_pressure == "active_squeeze":
        risk_tags.append("funding_squeeze_risk")

    # -------- Final Interpretation --------
    return {
        "position_direction": pos_dir,
        "crowd_bias": crowd_bias,
        "relationship": relationship,
        "implication": implication,
        "execution_confirmation": execution_confirmation,
        "stability": stability,
        "risk_tags": risk_tags,
    }


if __name__ == "__main__":
    market_state = {'symbol': 'BTCUSDT', 'ts': 1768046222742,
            'crowd_positioning': {'retail_sentiment': 'long', 'smart_money_sentiment': 'long', 'divergence': 'low',
                                  'fragility': 'high'}, 'market_state': {
            'short_term': {'direction': 'bearish', 'momentum': 'weakening', 'risk': 'high', 'confidence': 0.35},
            'mid_term': {'direction': 'neutral', 'momentum': 'neutral', 'confidence': 0.67},
            'long_term': {'direction': 'neutral', 'veto': True}},
            'crowd_state': {'bias': 'long', 'crowding_level': 'high', 'fragility': 'high',
                            'funding_pressure': 'potential_squeeze', 'consistency': 'conflicted'}}

    position_side = "SHORT"
    ctx = build_crowd_interpretation(market_state, position_side)
    print(ctx)
