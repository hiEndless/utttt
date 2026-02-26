"""
逐仓位的风控状态生成（跟随事件分析一起落库）

它是：
Position Risk Agent 的最终输出
单仓位、不可推导、可直接执行
不关心其他仓位、不关心账户整体

输入：
Position Risk Agent 输出（必需）
Signal Validation Agent 输出（可选）
previous_execution_state（可选）

输出：
execution_state（只描述 “当前与未来一段时间允许做什么”）

明确不做的事：
❌ 不推翻 risk_action
❌ 不重新判断方向
❌ 不修改 exposure_delta

用于：
Order Executor / Trade Router（执行层）：校验账户级是否允许

自动交易场景：
必须接入 execution_boundary_with_position_time.py 输出到 position_state_aggregator。
理由：
Execution Aggregator 的 cooldown 只针对 exit 类型或历史冷却，对“持仓时间红线”无法覆盖。
execution_boundary_with_position_time.py 可以提供 风险扩张类动作的禁止信息（open/add/scale_in），保证自动交易不会违反时间红线约束。
实现方式：
把 execution_constraint['forbidden_actions'] 作为 execution_constraint 参数传入 position_state_aggregator。
position_state_aggregator 在生成 action_allowance 时，可以额外剔除这些 forbidden_actions。

仅风控/人工交易场景：
可选接入，主要用于日志记录或提示。
position_state_aggregator 已经可以生成允许动作和 cooldown 信息，即使不接入，也不会影响人工决策安全。
"""
"""
逐仓位的风控状态生成（跟随事件分析一起落库）
"""
import time
import asyncio
import json
from typing import Optional, Dict, Any
from agent_server.utils.redis_client import RedisClient

COOLDOWN_SECONDS = 15 * 60  # 15 分钟

# --------------------------------------------
# risk_action → action_allowance（确定性映射）
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

COOLDOWN_EXIT_TYPES = {"risk", "emergency", "constraint_violation"}


# ==========================================================
# 风险语义推导（constraint 优先）
# ==========================================================
def _derive_risk_regime(signal_validation_output: Optional[Dict[str, Any]]) -> Optional[str]:
    if not signal_validation_output:
        return None

    audit = signal_validation_output.get("audit_confidence", {}) or {}
    structural = audit.get("structural_clarity")
    flags = signal_validation_output.get("risk_exposure_flags", []) or []

    if structural == "DOMINANT_CONFLICT":
        return "structural_conflict"

    if "crowding_risk" in flags:
        return "crowding_risk"

    return "normal"


# ==========================================================
# 外部执行约束（最高优先级）
# ==========================================================
def _apply_execution_constraint(
        allowance: Dict[str, bool],
        execution_constraint: Dict[str, Any]
) -> Dict[str, bool]:
    allowance = allowance.copy()
    allowed = execution_constraint.get("allowed_actions")
    forbidden = execution_constraint.get("forbidden_actions", [])

    # --- 白名单模式 ---
    if allowed:
        allowance["allow_open"] = "open" in allowed
        allowance["allow_add"] = any(
            a in allowed for a in ["add", "aggressive_add", "scale_in_small"]
        )
        allowance["allow_hold"] = "hold" in allowed
        allowance["allow_reduce"] = "reduce" in allowed
        allowance["allow_close"] = "close" in allowed

    # --- 黑名单覆盖 ---
    for action in forbidden:
        if action == "open":
            allowance["allow_open"] = False
        if action in ("add", "aggressive_add", "scale_in_small"):
            allowance["allow_add"] = False
        if action == "reverse_position":
            allowance["allow_open"] = False
            allowance["allow_add"] = False

    return allowance


def aggregate_execution_state(
        risk_action_output: Dict[str, Any],
        previous_execution_state: Optional[Dict[str, Any]] = None,
        execution_constraint: Optional[Dict[str, Any]] = None,
        now_ts: Optional[int] = None
) -> Dict[str, Any]:
    now_ts = now_ts or int(time.time())
    risk_action = risk_action_output["risk_action"]
    meta = risk_action_output.get("meta", {}) or {}
    exit_type = meta.get("exit_type", "structural")

    allowance = RISK_ACTION_TO_ALLOWANCE.get(risk_action, {}).copy()
    system_info: Dict[str, Any] = {}

    # ------------------------------
    # 冷却继承
    # ------------------------------
    execution_regime = "normal"
    in_cooldown = False
    cooldown_until = None

    if previous_execution_state:
        prev_exec = previous_execution_state.get("execution_state", {})
        prev_cd = prev_exec.get("cooldown_state", {})
        if prev_cd.get("in_cooldown") and prev_cd.get("until_ts", 0) > now_ts:
            in_cooldown = True
            cooldown_until = prev_cd["until_ts"]
            execution_regime = "cooldown"

    # 本次 exit 触发冷却
    if risk_action == "exit" and exit_type in COOLDOWN_EXIT_TYPES:
        in_cooldown = True
        cooldown_until = now_ts + COOLDOWN_SECONDS
        execution_regime = "cooldown"
        system_info["cooldown_trigger"] = {
            "exit_type": exit_type,
            "duration_sec": COOLDOWN_SECONDS
        }

    if in_cooldown:
        allowance["allow_open"] = False
        allowance["allow_add"] = False

    # ------------------------------
    # execution_constraint（最高优先级）
    # ------------------------------
    if execution_constraint:
        allowance = _apply_execution_constraint(allowance, execution_constraint)
        system_info["constraint_applied"] = True
        system_info["constraint_reason_tags"] = execution_constraint.get(
            "constraint_reason_tags", []
        )

    # ------------------------------
    # 风险语义（constraint 优先）
    # ------------------------------
    risk_regime = execution_constraint["risk_bias"]

    return {
        "execution_state": {
            "risk_regime": risk_regime,
            "execution_regime": execution_regime,
            "intent_bias": execution_constraint.get("intent_bias") if execution_constraint else None,
            "action_allowance": allowance,
            "cooldown_state": {
                "in_cooldown": in_cooldown,
                "until_ts": cooldown_until
            },
            "system_info": system_info
        }
    }


# ==========================================================
# 执行态老化
# ==========================================================
def age_execution_state(
        execution_state_payload: Dict[str, Any],
        now_ts: Optional[int] = None
) -> Dict[str, Any]:
    now_ts = now_ts or int(time.time())
    new_payload = json.loads(json.dumps(execution_state_payload))
    exec_state = new_payload.get("execution_state", {})
    cooldown = exec_state.get("cooldown_state", {})
    allowance = exec_state.get("action_allowance", {})

    if cooldown.get("in_cooldown"):
        until = cooldown.get("until_ts", 0)
        if until and now_ts > until:
            cooldown["in_cooldown"] = False
            cooldown["until_ts"] = None
            exec_state["execution_regime"] = "normal"

            # 仅恢复冷却限制
            allowance["allow_open"] = True
            allowance["allow_add"] = True

    exec_state["action_allowance"] = allowance
    exec_state["cooldown_state"] = cooldown
    new_payload["execution_state"] = exec_state

    return new_payload


def key(exchange: str, trade_id: str, symbol: str) -> str:
    return (
        f"risk:execution:"
        f"{(exchange or '').lower()}:"
        f"{(symbol or '').upper()}:"
        f"{(trade_id or 'default').lower()}:"
    )


async def store_aggregate_execution_state(
        *,
        exchange: str,
        trade_id: str,
        symbol: str,
        execution_state: Dict[str, Any],
        redis_db: int | None = None,
        ttl_seconds: int | None = None,
) -> str:
    rc = RedisClient(db=redis_db)
    k = key(exchange=exchange, trade_id=trade_id, symbol=symbol)
    await rc.set_json(k, execution_state, ex=ttl_seconds)
    return k


async def aggregate_execution_state_and_store(
        risk_action_output: Dict[str, Any],
        previous_execution_state: Optional[Dict[str, Any]] = None,
        execution_constraint: Optional[Dict[str, Any]] = None,
        now_ts: Optional[int] = None,
        *,
        exchange: str | None = None,
        trade_id: str | None = None,
        symbol: str | None = None,
        redis_db: int | None = None,
        ttl_seconds: int = 900,
) -> Dict[str, Any]:
    execution_state = aggregate_execution_state(
        risk_action_output=risk_action_output,
        previous_execution_state=previous_execution_state,
        execution_constraint=execution_constraint,
        now_ts=now_ts,
    )

    meta = risk_action_output.get("meta") if isinstance(risk_action_output, dict) else {}
    ex = exchange if exchange is not None else meta.get("exchange")
    td = trade_id if trade_id is not None else meta.get("trade_id")
    sym = symbol if symbol is not None else meta.get("symbol")

    await store_aggregate_execution_state(
        exchange=str(ex or ""),
        trade_id=str(td or "default"),
        symbol=str(sym or ""),
        execution_state=execution_state,
        redis_db=redis_db,
        ttl_seconds=ttl_seconds,
    )
    return execution_state


if __name__ == "__main__":
    now = int(time.time())

    # -------------------------------
    # 1️⃣ 普通 exit（无冷却）
    # -------------------------------
    risk_action_output = {
        "risk_action": "exit",
        "meta": {"exit_type": "structural"}
    }

    result1 = aggregate_execution_state(
        risk_action_output=risk_action_output,
        now_ts=now
    )
    print("\n[CASE 1] Structural Exit")
    print(json.dumps(result1, indent=2))

    # -------------------------------
    # 2️⃣ 风险 exit（触发冷却）
    # -------------------------------
    risk_action_output2 = {
        "risk_action": "exit",
        "meta": {"exit_type": "risk"}
    }

    result2 = aggregate_execution_state(
        risk_action_output=risk_action_output2,
        now_ts=now
    )
    print("\n[CASE 2] Risk Exit → Cooldown")
    print(json.dumps(result2, indent=2))

    # -------------------------------
    # 3️⃣ 冷却继承
    # -------------------------------
    result3 = aggregate_execution_state(
        risk_action_output={"risk_action": "hold"},
        previous_execution_state=result2,
        now_ts=now + 60
    )
    print("\n[CASE 3] Inherited Cooldown")
    print(json.dumps(result3, indent=2))

    # -------------------------------
    # 4️⃣ 冷却老化
    # -------------------------------
    aged = age_execution_state(result2, now_ts=now + COOLDOWN_SECONDS + 10)
    print("\n[CASE 4] Cooldown Aged")
    print(json.dumps(aged, indent=2))

    # -------------------------------
    # 5️⃣ execution_constraint 生效
    # -------------------------------
    execution_constraint = {
        "intent_bias": "bullish",
        "allowed_actions": ["hold", "reduce"],
        "forbidden_actions": ["open", "scale_in_small"],
        "risk_bias": "defensive",
        "constraint_reason_tags": ["dominant_structural_conflict"]
    }

    result5 = aggregate_execution_state(
        risk_action_output={"risk_action": "scale_in_small"},
        execution_constraint=execution_constraint,
        now_ts=now
    )
    print("\n[CASE 5] Constraint Applied")
    print(json.dumps(result5, indent=2))
