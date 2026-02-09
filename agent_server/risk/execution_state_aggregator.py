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


def key(
        exchange: str,
        trade_id: str,
        symbol: str
) -> str:
    # 中文注释：逐仓位“时间状态/执行状态”的 Redis Key（按交易账户 + 标的 + trade_id 分桶）
    return (
        f"risk:"
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
    """
    将 aggregate_execution_state 的结果写入 Redis（覆盖写）。
    - ttl_seconds: 可选 TTL（秒），用于避免旧状态长期残留
    """
    rc = RedisClient(db=redis_db)
    k = key(exchange=exchange, trade_id=trade_id, symbol=symbol)
    await rc.set_json(k, execution_state, ex=ttl_seconds)
    return k


async def aggregate_execution_state_and_store(
        risk_action_output: Dict[str, Any],
        signal_validation_output: Optional[Dict[str, Any]] = None,
        previous_execution_state: Optional[Dict[str, Any]] = None,
        now_ts: Optional[int] = None,
        *,
        exchange: str | None = None,
        trade_id: str | None = None,
        symbol: str | None = None,
        redis_db: int | None = None,
        ttl_seconds: int | None = None,
) -> Dict[str, Any]:
    """
    生成 execution_state 并落库到 Redis。
    - exchange/trade_id/symbol：若未显式传入，会尝试从 risk_action_output["meta"] 取值
    """
    execution_state = aggregate_execution_state(
        risk_action_output=risk_action_output,
        signal_validation_output=signal_validation_output,
        previous_execution_state=previous_execution_state,
        now_ts=now_ts,
    )

    meta = risk_action_output.get("meta") if isinstance(risk_action_output, dict) else None
    if not isinstance(meta, dict):
        meta = {}
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
