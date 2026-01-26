from typing import Dict, Any


def abstract_trade_event(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert raw trade execution data into
    Trade Event Analysis Agent compatible abstract representation.
    """

    action = str(raw.get("action")).upper()
    position_side = raw.get("position_side")

    # ---- 1. Trade Core ----
    trade_core = {
        # "trade_id": raw.get("trade_id"),
        "position_side": position_side,
        "action": action,
        "size_change": {
            "direction": "DECREASE" if action in ("CLOSE", "REDUCE") else "INCREASE",
            "absolute": action == "CLOSE"
        }
    }

    # ---- 2. Position Effect ----
    if action == "CLOSE":
        post_state = "FLAT"
        exposure_change = "REDUCE"
    elif action == "REDUCE":
        post_state = "PARTIAL"
        exposure_change = "REDUCE"
    else:
        post_state = "OPEN"
        exposure_change = "INCREASE"

    position_effect = {
        "exposure_change": exposure_change,
        "post_action_state": post_state
    }

    # ---- 3. PnL / Risk Context (Abstracted) ----
    pnl_ratio = float(raw.get("pnl_ratio", 0))

    if pnl_ratio > 0.002:
        pnl_state = "PROFIT"
        pnl_bias = "FAVORABLE"
    elif pnl_ratio < -0.002:
        pnl_state = "LOSS"
        pnl_bias = "ADVERSE"
    else:
        pnl_state = "BREAKEVEN"
        pnl_bias = "NEUTRAL"

    # 对 CLOSE 行为给出“退出语义”
    exit_type = None
    if action == "CLOSE":
        exit_type = "DEFENSIVE" if pnl_bias == "ADVERSE" else "TACTICAL"

    position_context = {
        "pnl_state": pnl_state,
        "pnl_bias": pnl_bias,
        **({"exit_type": exit_type} if exit_type else {})
    }

    # ---- 4. Event Meta ----
    # event_meta = {
    #     "event_type": "TRADE_EVENT",
    #     "final_event": True
    # }

    return {
        "trade_core": trade_core,
        "position_effect": position_effect,
        "position_context": position_context,
        # "event_meta": event_meta
    }
