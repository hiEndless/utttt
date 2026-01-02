"""
串行单脚本
信号确认 → 写产出 → 立即串行更新时序状态
Temporal State Reducer
- 对 temporal 事件进行序列化reduce
- 维护每个 symbol/position_side 的状态（valid_streak, invalid_streak, conflict_streak, holding_duration_min, last_verdict, last_update_ts, entry_ts）
- 状态更新规则：
    - INVALID：invalid_streak +1, valid_streak, conflict_streak 重置为 0
    - CONFLICT：conflict_streak +1, valid_streak, invalid_streak 重置为 0
    - VALID：valid_streak +1, invalid_streak, conflict_streak 重置为 0
- 状态更新触发条件：
    - 每次收到新事件时
    - 状态持续时间超过 1 分钟（holding_duration_min 重置为 0）
- 状态输出：
    - 每个 symbol/position_side 的最新状态
"""

import json
from typing import Any, Dict
from agent_server.utils.redis_client import RedisClient
import time


def _latest_key(exchange: str, account_id: str, symbol: str, position_side: str) -> str:
    ex = (exchange or "").lower()
    acc = (account_id or "default").lower()
    sym = symbol or ""
    side = (position_side or "NA").upper()
    return f"risk_temporal:{ex}:{acc}:{sym}:{side}:latest"


async def reduce_once(exchange: str, account_id: str, symbol: str, position_side: str, verdict: str, ts: int, confidence_numeric: float | None = None) -> Dict[str, Any]:
    rc = RedisClient()
    key = _latest_key(exchange, account_id, symbol, position_side)
    v = await rc.get(key)
    try:
        cur = json.loads(v or "{}") if v else {}
    except Exception:
        cur = {}
    invalid = int(cur.get("invalid_streak") or 0)
    conflict = int(cur.get("conflict_streak") or 0)
    valid = int(cur.get("valid_streak") or 0)
    last_verdict = cur.get("last_verdict")
    entry_ts = int(cur.get("entry_ts") or ts)
    now_ts = int(ts or int(time.time() * 1000))
    if (verdict or "").upper() == "INVALID":
        invalid += 1
        conflict = 0
        valid = 0
    elif (verdict or "").upper() == "CONFLICT":
        conflict += 1
        invalid = 0
        valid = 0
    else:
        valid += 1
        invalid = 0
        conflict = 0
    holding_duration_min = max(0, int((now_ts - entry_ts) / 60000))
    out = {
        "holding_duration_min": holding_duration_min,
        "last_verdict": (verdict or last_verdict or "").upper(),
        "invalid_streak": invalid,
        "conflict_streak": conflict,
        "valid_streak": valid,
        "last_update_ts": now_ts,
        "entry_ts": entry_ts,
    }
    await rc.set_json(key, out)
    return out
