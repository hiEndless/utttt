from typing import Dict, Literal, Optional, Any

PositionDirection = Literal["long", "short", "flat"]


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
                if abs(zval) >= 1.5 and abs(dval) >= 0.01:
                    return True
        return False

    crowd_extreme = _max_abs_zscore(["15m", "30m", "1h", "4h"]) >= 2.0
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
        if (crowding_level == "high" and (crowd_extreme or crowd_building)) or fragility == "high":
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
