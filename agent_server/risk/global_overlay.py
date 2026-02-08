"""
全局账户风控状态（跟随事件分析一起落库）

后续做全账户熔断、账户级风险模式切换、极端异常保护时再使用account_risk_state
目前account_risk_state先占位

它是：
多个 execution_state 的 收敛结果
只会 收紧，不会放松
不做行情判断、不做仓位分析

读取：
execution_state（全部仓位）
Global Overlay（上一次）
account_risk_state（占位，下次迭代使用，熔断专用）

用于：
Signal Validation Agent（信号确认）：判断“这个信号，在当前账户风险环境下，是否还值得被执行”
任何开仓类 agent
Order Executor / Trade Router（执行层）：校验账户级是否允许
"""

from typing import List, Dict, Optional
import time

RISK_REGIME_RANK = {
    "normal": 0,
    "elevated": 1,
    "critical": 2
}


def now_ts() -> int:
    """Return current unix timestamp (seconds)."""
    return int(time.time())


def aggregate_global_overlay(
        execution_states: List[Dict],
        account_risk_state: Dict,
        prev_global_overlay_state: Optional[Dict] = None,
        current_ts: Optional[int] = None
) -> Dict:
    """
    Global Overlay v1 (Minimal Viable Version)

    Parameters
    ----------
    execution_states : List[Dict]
        List of per-position execution states, e.g.
        [
          {
            "symbol": "ETHUSDT",
            "execution_state": {
              "risk_regime": "elevated",
              "action_allowance": {...},
              "cooldown_state": {...}
            }
          }
        ]

    account_risk_state : Dict
        Account-level risk snapshot (balance, available_pct, etc.)
        NOTE: v1 does not actively gate on this, only reserves interface.

    prev_global_overlay_state : Optional[Dict]
        Last global overlay state (if exists), used only to prevent
        cooldown flip-flop.

    current_ts : Optional[int]
        Current timestamp (seconds). Defaults to now().
    """

    if not execution_states:
        raise ValueError("execution_states must not be empty")

    current_ts = current_ts or now_ts()

    # --------------------------------------------------
    # 1. Aggregate global risk regime (MAX principle)
    # --------------------------------------------------
    global_risk_regime = max(
        execution_states,
        key=lambda x: RISK_REGIME_RANK.get(
            x["execution_state"]["risk_regime"], 0
        )
    )["execution_state"]["risk_regime"]

    # --------------------------------------------------
    # 2. Aggregate action allowance (conservative AND)
    # --------------------------------------------------
    allow_open = all(
        es["execution_state"]["action_allowance"].get("allow_open", False)
        for es in execution_states
    )

    allow_add = all(
        es["execution_state"]["action_allowance"].get("allow_add", False)
        for es in execution_states
    )

    # Global overlay NEVER blocks risk reduction / exit
    global_action_allowance = {
        "allow_open": allow_open,
        "allow_add": allow_add,
        "allow_hold": True,
        "allow_reduce": True,
        "allow_close": True
    }

    # --------------------------------------------------
    # 3. Aggregate cooldown state (inherit-only)
    # --------------------------------------------------
    cooldown_until_candidates = []

    for es in execution_states:
        cd = es["execution_state"].get("cooldown_state", {})
        if cd.get("in_cooldown"):
            cooldown_until_candidates.append(cd.get("until_ts", 0))

    computed_in_cooldown = len(cooldown_until_candidates) > 0
    computed_until_ts = (
        max(cooldown_until_candidates)
        if cooldown_until_candidates else None
    )

    # --------------------------------------------------
    # 4. Merge previous global overlay (anti flip-flop)
    # --------------------------------------------------
    if prev_global_overlay_state:
        prev_cd = prev_global_overlay_state.get("global_cooldown_state", {})
        if prev_cd.get("in_cooldown"):
            computed_in_cooldown = True
            if computed_until_ts is None:
                computed_until_ts = prev_cd.get("until_ts")
            else:
                computed_until_ts = max(
                    computed_until_ts,
                    prev_cd.get("until_ts", 0)
                )

    global_cooldown_state = {
        "in_cooldown": computed_in_cooldown,
        "until_ts": computed_until_ts
    }

    # --------------------------------------------------
    # 5. Final Global Overlay State
    # --------------------------------------------------
    return {
        "global_risk_regime": global_risk_regime,
        "global_action_allowance": global_action_allowance,
        "global_cooldown_state": global_cooldown_state,
        "meta": {
            # "derived_from": [es.get("symbol") for es in execution_states],
            "updated_at": current_ts
        }
    }


if __name__ == "__main__":
    execution_state = {'execution_state': {'risk_regime': 'elevated',
                                           'action_allowance': {'allow_open': False, 'allow_add': False,
                                                                'allow_hold': False, 'allow_reduce': False,
                                                                'allow_close': True},
                                           'cooldown_state': {'in_cooldown': True, 'until_ts': 1770574916}}}
    account_risk_state = {"balance": 43.06110522, "available_pct": 0.9494231736767299, "position_occupancy_ratio": 0.05047561642682798}
    global_overlay = aggregate_global_overlay([execution_state], account_risk_state)
    print(global_overlay)
