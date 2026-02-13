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

# 哪些 exit 类型需要冷却
COOLDOWN_EXIT_TYPES = {"risk", "emergency", "constraint_violation"}


def aggregate_execution_state(
    risk_action_output: Dict[str, Any],
    signal_validation_output: Optional[Dict[str, Any]] = None,
    previous_execution_state: Optional[Dict[str, Any]] = None,
    execution_constraint: Optional[Dict[str, Any]] = None,
    decision_output: Optional[Dict[str, Any]] = None,
    now_ts: Optional[int] = None
) -> Dict[str, Any]:
    now_ts = now_ts or int(time.time())

    risk_action = risk_action_output["risk_action"]
    meta = risk_action_output.get("meta", {}) or {}

    # ---------- exit 类型（新增） ----------
    # 默认认为是结构性 exit（不惩罚）
    exit_type = meta.get("exit_type", "structural")

    # ---------- 基础权限 ----------
    allowance = RISK_ACTION_TO_ALLOWANCE.get(risk_action, {}).copy()

    system_info: Dict[str, Any] = {}

    # ---------- 防止“被约束逼出 exit”的安全网 ----------
    if risk_action == "exit":
        forbidden = execution_constraint.get("forbidden_actions", []) if execution_constraint else []

        is_hold_forbidden = "hold" in forbidden
        is_reduce_forbidden = "reduce" in forbidden

        decision_supports_exit = False
        if decision_output:
            d_intent = str(decision_output.get("trade_intent", "")).lower()
            d_action = str(decision_output.get("action", "")).lower()
            if any(k in d_intent for k in ("exit", "close")) or any(k in d_action for k in ("exit", "close")):
                decision_supports_exit = True

        if is_hold_forbidden and is_reduce_forbidden and not decision_supports_exit:
            allowance["allow_hold"] = True
            allowance["allow_reduce"] = True
            system_info["forced_exit_override"] = True
            system_info["reason"] = (
                "Detected self-locking constraint without explicit decision-level exit. "
                "Downgraded to allow hold/reduce."
            )

    # ---------- 冷却与执行态 ----------
    execution_regime = "normal"
    in_cooldown = False
    cooldown_until = None

    # 继承历史冷却
    if previous_execution_state:
        prev_exec = previous_execution_state.get("execution_state", {})
        prev_cd = prev_exec.get("cooldown_state", {})
        if prev_cd.get("in_cooldown") and prev_cd.get("until_ts", 0) > now_ts:
            in_cooldown = True
            cooldown_until = prev_cd["until_ts"]
            execution_regime = "cooldown"

    # 本次 exit 是否触发冷却
    if risk_action == "exit" and exit_type in COOLDOWN_EXIT_TYPES:
        in_cooldown = True
        cooldown_until = now_ts + COOLDOWN_SECONDS
        execution_regime = "cooldown"
        system_info["cooldown_trigger"] = {
            "exit_type": exit_type,
            "duration_sec": COOLDOWN_SECONDS
        }

    # 冷却期限制（只限制开仓 / 加仓）
    if in_cooldown:
        allowance["allow_open"] = False
        allowance["allow_add"] = False

    # ---------- 结构性风险语义（只读） ----------
    risk_regime = None
    if signal_validation_output:
        risk_regime = signal_validation_output.get("risk_implication")

    return {
        "execution_state": {
            "risk_regime": risk_regime,              # 结构语义（不可被 aging 改）
            "execution_regime": execution_regime,    # 执行态（可 aging）
            "action_allowance": allowance,
            "cooldown_state": {
                "in_cooldown": in_cooldown,
                "until_ts": cooldown_until
            },
            "system_info": system_info
        }
    }


def age_execution_state(
    execution_state_payload: Dict[str, Any],
    now_ts: Optional[int] = None
) -> Dict[str, Any]:
    """
    仅对执行态进行老化：
    - 冷却结束 → 解除冷却限制
    - 不修改 risk_regime
    """
    now_ts = now_ts or int(time.time())

    new_payload = json.loads(json.dumps(execution_state_payload))
    exec_state = new_payload.get("execution_state", {})
    cooldown = exec_state.get("cooldown_state", {})
    allowance = exec_state.get("action_allowance", {})

    changed = False

    if cooldown.get("in_cooldown"):
        until = cooldown.get("until_ts", 0)
        if until and now_ts > until:
            cooldown["in_cooldown"] = False
            cooldown["until_ts"] = None
            exec_state["execution_regime"] = "normal"

            # 只解除冷却带来的限制
            allowance["allow_open"] = True
            allowance["allow_add"] = True

            changed = True

    if changed:
        exec_state["action_allowance"] = allowance
        exec_state["cooldown_state"] = cooldown
        new_payload["execution_state"] = exec_state

        if "meta" in new_payload:
            new_payload["meta"]["updated_at"] = now_ts

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
    signal_validation_output: Optional[Dict[str, Any]] = None,
    previous_execution_state: Optional[Dict[str, Any]] = None,
    execution_constraint: Optional[Dict[str, Any]] = None,
    decision_output: Optional[Dict[str, Any]] = None,
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
        signal_validation_output=signal_validation_output,
        previous_execution_state=previous_execution_state,
        execution_constraint=execution_constraint,
        decision_output=decision_output,
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
        ],
        "meta": {"symbol": "ETHUSDT", "exchange": "binance", "event_id": "ETHUSDT.final.1770290252305",
                 "event_type": "mixed", "ts": 1770627390376, "version": "v1.0", "direction": "bullish",
                 "trade_id": "9cedf3d0770041c8b11856c35ef664a2"}
    }

    signal_validation_output = {"verdict": "ATTENUATE", "structural_alignment": "PARTIAL_CONFLICT",
                                "risk_implication": "elevated",
                                "reasoning": ["多周期结构存在轻度冲突，建议降低仓位与加仓强度"],
                                "meta": {"symbol": "ETHUSDT", "exchange": "binance",
                                         "event_id": "ETHUSDT.final.1770290252305",
                                         "event_type": "mixed", "ts": 1770304117868, "version": "v1.0",
                                         "direction": "bullish"}}

    async def _demo():
        execution_state = await aggregate_execution_state_and_store(
            risk_action_output=risk_action_output,
            signal_validation_output=signal_validation_output,
        )
        print(json.dumps(execution_state, ensure_ascii=False))

    asyncio.run(_demo())
