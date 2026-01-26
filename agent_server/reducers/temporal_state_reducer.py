import json
import time
from typing import Dict, Any, Optional

from agent_server.utils.redis_client import RedisClient

# =========================
# 全局配置
# =========================

STREAK_CAP = 3  # 风控语义上限，0~3 即可
TIME_MS_IN_MIN = 60_000


# =========================
# Redis Key
# =========================

def temporal_key(
        exchange: str,
        trade_id: str,
        symbol: str,
        position_side: str,
) -> str:
    return (
        f"risk:temporal_state:"
        f"{(exchange or '').lower()}:"
        f"{(trade_id or 'default').lower()}:"
        f"{(symbol or '').upper()}:"
        f"{(position_side or '').upper()}"
    )


# =========================
# Reducer 核心
# =========================

async def reduce_temporal_state(
        *,
        exchange: str,
        trade_id: str,
        symbol: str,
        position_side: str,  # LONG / SHORT
        verdict: str,  # INVALID / WEAK_VALID / VALID
        alignment: Optional[str] = None,  # STRONGLY_CONFLICT / CONFLICT / ALIGNED
        entry_ts: int,  # 由 Position Tracker 提供
        event_ts: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Deterministic Temporal State Reducer

    - 不扫描仓位
    - 不推断 entry_ts
    - 只压缩 verdict/alignment 序列
    """

    rc = RedisClient()
    key = temporal_key(exchange, trade_id, symbol, position_side)

    now_ts = int(event_ts or time.time() * 1000)
    verdict = (verdict or "").upper()
    alignment = (alignment or "").upper()

    # -------------------------
    # 读取旧状态（如果不存在则初始化）
    # -------------------------
    raw = await rc.get(key)
    try:
        prev = json.loads(raw) if raw else {}
    except Exception:
        prev = {}

    # 关键修复：在覆盖 last_update_ts 之前先捕获“上一次事件时间”，否则 time_since_last_event_min 会被错误算成 0
    prev_last_update_ts = int(prev.get("last_update_ts", 0) or 0)
    time_since_last_event_min = (
        max(0, int((now_ts - prev_last_update_ts) / TIME_MS_IN_MIN))
        if prev_last_update_ts > 0
        else 0
    )

    invalid_streak = int(prev.get("invalid_streak", 0))
    conflict_streak = int(prev.get("conflict_streak", 0))
    valid_streak = int(prev.get("valid_streak", 0))

    # -------------------------
    # Streak 状态机（核心逻辑）
    # -------------------------
    
    # 1. 致命风险 (INVALID / STRONGLY_CONFLICT)
    if verdict == "INVALID" or alignment == "STRONGLY_CONFLICT":
        invalid_streak = min(invalid_streak + 1, STREAK_CAP)
        conflict_streak = 0
        valid_streak = 0

    # 2. 结构冲突 (WEAK_VALID / CONFLICT)
    # 注意：旧代码中的 verdict="CONFLICT" 映射到此处
    elif verdict == "WEAK_VALID" or verdict == "CONFLICT" or alignment == "CONFLICT":
        conflict_streak = min(conflict_streak + 1, STREAK_CAP)
        invalid_streak = 0
        valid_streak = 0

    # 3. 结构一致 (VALID / ALIGNED)
    # 必须 alignment 也为 ALIGNED (或为空以兼容旧逻辑)
    elif verdict in ("VALID", "STRONG"):
        # 如果 alignment 存在且不为 ALIGNED，则不能算完全 VALID Streak (降级处理)
        if alignment and alignment != "ALIGNED":
             # 这种情况理论上不应发生(已被上面捕获)，但作为兜底，归入 conflict
             conflict_streak = min(conflict_streak + 1, STREAK_CAP)
             invalid_streak = 0
             valid_streak = 0
        else:
            valid_streak = min(valid_streak + 1, STREAK_CAP)
            invalid_streak = 0
            conflict_streak = 0

    else:
        # 未知 verdict：保持原状态（不建议，但安全）
        pass

    # -------------------------
    # 时间派生字段（只读 entry_ts）
    # -------------------------
    holding_duration_min = max(
        0,
        int((now_ts - int(entry_ts)) / TIME_MS_IN_MIN)
    )

    # -------------------------
    # 新状态（完整覆盖）
    # -------------------------
    state = {
        "entry_ts": int(entry_ts),
        "holding_duration_min": holding_duration_min,

        "prev_update_ts": prev_last_update_ts,
        "time_since_last_event_min": time_since_last_event_min,

        "last_verdict": verdict,
        "last_alignment": alignment,  # 新增字段记录

        "invalid_streak": invalid_streak,
        "conflict_streak": conflict_streak,
        "valid_streak": valid_streak,

        "last_update_ts": now_ts,
    }

    # -------------------------
    # 覆盖写入 Redis
    # -------------------------
    await rc.set_json(key, state)

    return state


if __name__ == "__main__":
    import asyncio


    async def _demo():
        state = await reduce_temporal_state(
            exchange="binance",
            trade_id="acc_1",
            symbol="BTCUSDT",
            position_side="LONG",
            verdict="WEAK_VALID",
            alignment="CONFLICT",
            entry_ts=int(time.time() * 1000) - 3600000,
            event_ts=int(time.time() * 1000),
        )
        print(json.dumps(state, ensure_ascii=False))


    asyncio.run(_demo())
