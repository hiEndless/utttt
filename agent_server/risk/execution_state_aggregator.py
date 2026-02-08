"""
输入：
Position Risk Agent 输出（必需）
Signal Validation Agent 输出（可选）
Account Risk State（可选）
previous_execution_state（可选）

输出：
execution_state（只描述 “当前与未来一段时间允许做什么”）

明确不做的事：
❌ 不推翻 risk_action
❌ 不重新判断方向
❌ 不修改 exposure_delta
"""
import time
from typing import Optional, Dict, Any

COOLDOWN_SECONDS = 15 * 60  # 15 minutes

# --------------------------------------------
# risk_action → action_allowance(确定性映射表)
# --------------------------------------------
RISK_ACTION_TO_ALLOWANCE = {
    "exit": {
        "allow_open": False,
        "allow_add": False,
        "allow_hold": False,
        "allow_reduce": False,
        "allow_close": True
    },
    "reduce": {
        "allow_open": False,
        "allow_add": False,
        "allow_hold": True,
        "allow_reduce": True,
        "allow_close": True
    },
    "hold": {
        "allow_open": False,
        "allow_add": False,
        "allow_hold": True,
        "allow_reduce": True,
        "allow_close": True
    },
    "scale_in_small": {
        "allow_open": False,
        "allow_add": True,
        "allow_hold": True,
        "allow_reduce": True,
        "allow_close": True
    }
}


def aggregate_execution_state(
        risk_action_output: Dict[str, Any],
        signal_validation_output: Optional[Dict[str, Any]] = None,
        previous_execution_state: Optional[Dict[str, Any]] = None,
        now_ts: Optional[int] = None
) -> Dict[str, Any]:
    now_ts = now_ts or int(time.time())

    risk_action = risk_action_output["risk_action"]

    # ---------- base allowance from risk_action ----------
    allowance = RISK_ACTION_TO_ALLOWANCE.get(risk_action, {}).copy()

    # ---------- cooldown handling ----------
    in_cooldown = False
    cooldown_until = None

    # inherit previous cooldown if exists
    if previous_execution_state:
        prev_cd = previous_execution_state.get("cooldown_state", {})
        if prev_cd.get("in_cooldown") and prev_cd.get("until_ts", 0) > now_ts:
            in_cooldown = True
            cooldown_until = prev_cd["until_ts"]

    # trigger new cooldown on exit
    if risk_action == "exit":
        in_cooldown = True
        cooldown_until = now_ts + COOLDOWN_SECONDS

    # apply cooldown constraints
    if in_cooldown:
        allowance["allow_open"] = False
        allowance["allow_add"] = False

    # ---------- risk regime label（弱语义，仅解释） ----------
    risk_regime = None
    if signal_validation_output:
        risk_regime = signal_validation_output.get("risk_implication")

    return {
        "execution_state": {
            "risk_regime": risk_regime,
            "action_allowance": allowance,
            "cooldown_state": {
                "in_cooldown": in_cooldown,
                "until_ts": cooldown_until
            }
        }
    }


if __name__ == "__main__":
    risk_action_output = {
        "risk_action": "exit",
        "exposure_delta": {
            "type": "percentage",
            "value": -1.0
        },
        "rationale": [
            "长期结构明确为‘否决型’，表明当前持仓方向在宏观尺度上不具备持续合理性 。",
            "持仓已处于长期持有状态，但浮盈极低，未实现有效风险回报补偿，继续占用 敞口性价比不足。",
            "执行约束显示风险偏好保守，且置信度偏低，叠加结构冲突与风险升高标签， 强化退出必要性。",
            "当前仓位占用账户资金比例极低，平仓后对整体账户影响可控，符合风险控制 优先原则。"
        ]
    }

    signal_validation_output = {"verdict": "ATTENUATE", "structural_alignment": "PARTIAL_CONFLICT",
                                "risk_implication": "elevated",
                                "reasoning": ["多周期结构存在轻度冲突，建议降低仓位与加仓强度"],
                                "meta": {"symbol": "ETHUSDT", "exchange": "binance",
                                         "event_id": "ETHUSDT.final.1770290252305",
                                         "event_type": "mixed", "ts": 1770304117868, "version": "v1.0",
                                         "direction": "bullish"}}


    execution_state = aggregate_execution_state(risk_action_output, signal_validation_output)
    print(execution_state)
