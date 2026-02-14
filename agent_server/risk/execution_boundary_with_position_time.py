"""
（未来再接）
ExecutionConstraintAggregator v1.1.1 (Time-as-Redline)

职责：
- 基于 SignalValidation / Decision / Position Time Semantics
- 生成“确定性、可执行”的 execution_constraint
- 不推理仓位状态、不裁决行为方向

输入: Signal Validation / Decision / Position Time Semantics
输出: forbidden_actions

功能更偏向 最终执行约束、安全屏障，面向 自动交易
核心价值是 保护资金安全、禁止超时或高风险加仓。
输出很简单：只要 forbidden_actions + meta。

| 功能/特性           | ExecutionBoundary（脚本1）                                          | ExecutionConstraintAggregator（脚本2）           |
| --------------- | --------------------------------------------------------------- | -------------------------------------------- |
| 位置              | Decision ↔ Position Risk                                        | Position Risk ↦ Execution Aggregator         |
| 输入              | Signal Validation + Decision                                    | Signal Validation + Decision + Position Time |
| 输出              | forbidden_actions + allowed_actions + intent_bias + reason_tags | forbidden_actions + meta                     |
| 硬性禁止（Hard Gate） | ✅                                                               | ✅                                            |
| 时间红线 / 仓位持有限制   | ❌                                                               | ✅                                            |
| 意图/方向偏向提示       | ✅（intent_bias）                                                  | ❌                                            |
| 允许动作/弱约束        | ✅（allowed_actions）                                              | ❌                                            |
| 面向场景            | 风控/人工操作                                                         | 自动交易/最终执行安全屏障                                |
| 可解释性            | 高                                                               | 中                                            |

接入位置：
Decision Agent
    ↓
ExecutionBoundary (风控约束+解释)
    ↓
Position Risk Agent
    ↓
ExecutionConstraintAggregator (时间红线+最终执行安全)
    ↓
position_state_aggregator / Order Executor


"""

from typing import Dict, Any, Optional
import time


# ------------------------------
# 时间红线（只允许 enum）
# ------------------------------
TIME_REDLINE_FLAGS = {
    "fatigue",        # 持仓过久，风险回报劣化
    "decay",          # 盈亏衰减期
    "overstayed",     # 明显超出预期周期
    "time_stop"       # 时间止损语义
}


def aggregate_execution_constraints(
    *,
    signal_validation_output: Optional[Dict[str, Any]] = None,
    decision_output: Optional[Dict[str, Any]] = None,
    position_time_semantics: Optional[Dict[str, Any]] = None,
    now_ts: Optional[int] = None
) -> Dict[str, Any]:
    """
    输出：
    execution_constraint = {
        forbidden_actions: [...],
        meta: {...}
    }
    """

    now_ts = now_ts or int(time.time())

    forbidden_actions = set()
    meta: Dict[str, Any] = {
        "version": "v1.1.1",
        "generated_at": now_ts
    }

    # -------------------------------------------------
    # Rule 1: Signal Validation（结构性信号裁剪）
    # -------------------------------------------------
    if signal_validation_output:
        verdict = str(signal_validation_output.get("verdict", "")).upper()

        if verdict in ("REJECT", "VETO"):
            forbidden_actions.update({"open", "add", "scale_in", "hold"})
            meta["signal_rule"] = "hard_veto"

        elif verdict in ("ATTENUATE",):
            forbidden_actions.update({"add", "scale_in"})
            meta["signal_rule"] = "attenuate"

    # -------------------------------------------------
    # Rule 2: Decision Safety（意图冲突裁剪）
    # -------------------------------------------------
    if decision_output:
        intent = str(decision_output.get("trade_intent", "")).lower()

        if intent in ("pause", "uncertain"):
            forbidden_actions.update({"open", "add", "scale_in"})
            meta["decision_rule"] = "intent_uncertain"

    # -------------------------------------------------
    # Rule 3: Time-as-Redline（唯一时间规则）
    # -------------------------------------------------
    if position_time_semantics:
        redline_flag = position_time_semantics.get("time_risk_flag")

        if redline_flag in TIME_REDLINE_FLAGS:
            # 只禁止“风险扩张类动作”
            forbidden_actions.update({"open", "add", "scale_in"})

            meta["time_redline"] = {
                "flag": redline_flag,
                "effect": "ban_exposure_increase"
            }

    # -------------------------------------------------
    # 安全兜底：永不禁止 close / reduce
    # -------------------------------------------------
    forbidden_actions.discard("close")
    forbidden_actions.discard("reduce")

    return {
        "execution_constraint": {
            "forbidden_actions": sorted(forbidden_actions),
            "meta": meta
        }
    }
