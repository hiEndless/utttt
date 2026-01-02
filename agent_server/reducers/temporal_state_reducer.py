import json
import time
from typing import Dict, Any, Optional

from agent_server.utils.redis_client import RedisClient

# =========================
# 全局配置
# =========================

STREAK_CAP = 3   # 风控语义上限，0~3 即可
TIME_MS_IN_MIN = 60_000


# =========================
# Redis Key
# =========================

def temporal_key(
    exchange: str,
    account_id: str,
    symbol: str,
    position_side: str,
) -> str:
    return (
        f"risk:temporal_state:"
        f"{(exchange or '').lower()}:"
        f"{(account_id or 'default').lower()}:"
        f"{(symbol or '').upper()}:"
        f"{(position_side or '').upper()}"
    )


# =========================
# Reducer 核心
# =========================

async def reduce_temporal_state(
    *,
    exchange: str,
    account_id: str,
    symbol: str,
    position_side: str,      # LONG / SHORT
    verdict: str,            # INVALID / CONFLICT / VALID / STRONG
    entry_ts: int,           # 由 Position Tracker 提供
    event_ts: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Deterministic Temporal State Reducer

    - 不扫描仓位
    - 不推断 entry_ts
    - 只压缩 verdict 序列
    """

    rc = RedisClient()
    key = temporal_key(exchange, account_id, symbol, position_side)

    now_ts = int(event_ts or time.time() * 1000)
    verdict = (verdict or "").upper()

    # -------------------------
    # 读取旧状态（如果不存在则初始化）
    # -------------------------
    raw = await rc.get(key)
    try:
        prev = json.loads(raw) if raw else {}
    except Exception:
        prev = {}

    invalid_streak = int(prev.get("invalid_streak", 0))
    conflict_streak = int(prev.get("conflict_streak", 0))
    valid_streak = int(prev.get("valid_streak", 0))

    # -------------------------
    # Streak 状态机（核心逻辑）
    # -------------------------
    if verdict == "INVALID":
        invalid_streak = min(invalid_streak + 1, STREAK_CAP)
        conflict_streak = 0
        valid_streak = 0

    elif verdict == "CONFLICT":
        conflict_streak = min(conflict_streak + 1, STREAK_CAP)
        invalid_streak = 0
        valid_streak = 0

    elif verdict in ("VALID", "STRONG"):
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

        "last_verdict": verdict,

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
