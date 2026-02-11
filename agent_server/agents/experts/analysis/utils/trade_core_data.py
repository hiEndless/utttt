import asyncio
from typing import Dict, Any, Tuple
from agent_server.utils.account import account_state


# ============================================================
# Utilities
# ============================================================

def classify_exposure(ratio: float) -> Tuple[str, float]:
    """
    Return exposure level and zone_position (0~1 within its band)
    """
    ratio = max(0.0, min(ratio, 1.0))

    if ratio < 0.3:
        level = "LOW"
        zone_position = ratio / 0.3
    elif ratio < 0.7:
        level = "MODERATE"
        zone_position = (ratio - 0.3) / 0.4
    else:
        level = "HIGH"
        zone_position = (ratio - 0.7) / 0.3

    return level, round(min(zone_position, 1.0), 4)


def classify_pnl(pnl_ratio: float) -> Tuple[str, str]:
    if pnl_ratio > 0.015:
        return "LATE_PROFIT", "FAVORABLE"
    elif pnl_ratio > 0.002:
        return "EARLY_PROFIT", "FAVORABLE"
    elif pnl_ratio < -0.015:
        return "LATE_LOSS", "ADVERSE"
    elif pnl_ratio < -0.002:
        return "EARLY_LOSS", "ADVERSE"
    else:
        return "BREAKEVEN", "NEUTRAL"


# ============================================================
# Account Info
# ============================================================

async def get_account_info(exchange: str):
    account_risk_state = await account_state(exchange)
    return (
        account_risk_state.get("balance", 0),
        account_risk_state.get("available_pct", 1.0)
    )


# ============================================================
# Main Abstraction
# ============================================================

async def abstract_trade_event(raw: Dict[str, Any]) -> Dict[str, Any]:

    action = str(raw.get("action")).upper()
    position_side = raw.get("position_side")
    exchange = raw.get("exchange")

    # ============================================================
    # 1. Behavior
    # ============================================================

    behavior = {
        "position_side": position_side,
        "action": action,
        "size_change": {
            "direction": "DECREASE" if action in ("CLOSE", "REDUCE") else "INCREASE",
            "absolute": action == "CLOSE"
        }
    }

    # ============================================================
    # 2. Exposure
    # ============================================================

    if action == "CLOSE":
        post_state = "FLAT"
        exposure_change = "REDUCE"
    elif action == "REDUCE":
        post_state = "PARTIAL"
        exposure_change = "REDUCE"
    else:
        post_state = "OPEN"
        exposure_change = "INCREASE"

    if position_side == "SHORT":
        directional_exposure = "DOWNWARD"
    elif position_side == "LONG":
        directional_exposure = "UPWARD"
    else:
        directional_exposure = "NEUTRAL"

    # ---- Account Snapshot ----
    balance, available_pct = await get_account_info(exchange)

    total_exposure_ratio = max(0.0, 1.0 - available_pct)
    account_level, account_zone = classify_exposure(total_exposure_ratio)

    # ---- Position Margin Ratio ----
    position_margin = float(raw.get("initialMargin", 0))
    margin_ratio = position_margin / balance if balance > 0 else 0.0
    margin_level, margin_zone = classify_exposure(margin_ratio)

    exposure = {
        "directional_exposure": directional_exposure,
        "exposure_change": exposure_change,
        "post_action_state": post_state,
        "current_total_exposure_level": account_level,
        "funds_utilization": {
            "account_exposure": {
                "ratio": round(total_exposure_ratio, 4),
                "level": account_level,
                "zone_position": account_zone
            },
            "position_allocation": {   # 保持你原字段名不变
                "ratio": round(margin_ratio, 4),
                "level": margin_level,
                "zone_position": margin_zone
            }
        }
    }

    # ============================================================
    # 3. Position Context
    # ============================================================

    pnl_ratio = float(raw.get("pnl_ratio", 0))
    pnl_state, pnl_bias = classify_pnl(pnl_ratio)

    exit_type = None
    if action == "CLOSE":
        exit_type = "DEFENSIVE" if pnl_bias == "ADVERSE" else "TACTICAL"

    position_context = {
        "pnl_state": pnl_state,
        "pnl_bias": pnl_bias,
        **({"exit_type": exit_type} if exit_type else {})
    }

    # ============================================================
    # 4. Holding Profile
    # ============================================================

    holding_horizon = raw.get("holding_horizon", "short_term")

    structure_dependency = (
        "short_term_dominant"
        if holding_horizon == "short_term"
        else "mid_term_dominant"
    )

    holding_profile = {
        "holding_horizon": holding_horizon,
        "structure_dependency": structure_dependency
    }

    # ============================================================
    # 5. Lifecycle（增强）
    # ============================================================

    position_phase = None
    phase_detail = None
    risk_intent = None

    if action == "OPEN":
        position_phase = "INITIATION"
        phase_detail = "NEW_POSITION"
        risk_intent = "RISK_ENTRY"

    elif action == "INCREASE":
        position_phase = "EXPANSION"

        if pnl_bias == "FAVORABLE":
            phase_detail = "CONFIRMATION_EXPANSION"
            risk_intent = "PRO_CYCLICAL"
        elif pnl_bias == "ADVERSE":
            phase_detail = "AVERAGING_DOWN"
            risk_intent = "COUNTER_TREND"
        else:
            phase_detail = "NEUTRAL_EXPANSION"
            risk_intent = "POSITION_BUILDING"

    elif action == "REDUCE":
        position_phase = "DE_RISKING"

        if pnl_bias == "FAVORABLE":
            phase_detail = "PROFIT_TAKING"
        elif pnl_bias == "ADVERSE":
            phase_detail = "DEFENSIVE_REDUCTION"
        else:
            phase_detail = "NEUTRAL_REDUCTION"

        risk_intent = "RISK_CONTRACTION"

    elif action == "CLOSE":
        position_phase = "EXIT"

        if pnl_bias == "ADVERSE":
            phase_detail = "DEFENSIVE_EXIT"
        else:
            phase_detail = "TACTICAL_EXIT"

        risk_intent = "TERMINATION"

    lifecycle = {
        "position_phase": position_phase,
        "phase_detail": phase_detail,
        "risk_intent": risk_intent
    }

    # ============================================================
    # 6. Risk State（新增）
    # ============================================================

    if exposure_change == "INCREASE":
        risk_regime = "EXPANSION"
    elif exposure_change == "REDUCE":
        risk_regime = "CONTRACTION"
    else:
        risk_regime = "STABLE"

    risk_state = {
        "risk_regime": risk_regime,
        "account_pressure_level": account_level,
        "position_pressure_level": margin_level,
        "pnl_pressure": pnl_bias
    }

    # ============================================================

    return {
        "behavior": behavior,
        "exposure": exposure,
        "position_context": position_context,
        "holding_profile": holding_profile,
        "lifecycle": lifecycle,
        "risk_state": risk_state
    }


# ============================================================
# Test (保持你的原测试结构)
# ============================================================

if __name__ == "__main__":

    trade_details = {
        'trade_id': 'e95cbad77cde4d8e80d405d1ff9a6f5f',
        'position_side': 'SHORT',
        'current_size': '-0.007',
        'entry_price': '3193.0',
        'mark_price': '3193.00000000',
        'pnl_ratio': '0.0',
        'action': 'OPEN',
        'change_amount': '-0.007',
        'initialMargin': 2.5,
        "exchange": "binance"
    }

    async def _demo():
        trade_core = await abstract_trade_event(trade_details)
        print(trade_core)

    asyncio.run(_demo())
