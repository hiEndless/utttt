from typing import Dict, Any


STATE_ENUMS = {
    "trend_state": {"unknown", "bullish", "bearish", "neutral", "weak_bullish", "weak_bearish"},
    "risk_state": {"unknown", "normal", "elevated", "high", "extreme"},
    "driver_state": {"unknown", "momentum_recovery", "liquidity_recovery", "funding_rise", "macro_calm"},
    "market_label": {"unknown", "vol_compression", "trend_acceleration", "range_bound"},
}


def validate_state(obj: Dict[str, Any]) -> bool:
    if not isinstance(obj, dict):
        return False
    for k, enums in STATE_ENUMS.items():
        v = obj.get(k)
        if v is not None and v not in enums:
            return False
    return True