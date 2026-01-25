import time
from typing import Dict, Any, List


# =========================
# 时间 Bucket
# =========================

def time_bucket(time_since_last_event_min: int) -> str:
    if time_since_last_event_min <= 60:
        return "T_1H"
    if time_since_last_event_min <= 120:
        return "T_2H"
    if time_since_last_event_min <= 240:
        return "T_4H"
    if time_since_last_event_min <= 720:
        return "T_12H"
    return "T_24H_PLUS"


# =========================
# Streak 权限表
# =========================

STREAK_PERMISSION = {
    "T_1H": "FULL",
    "T_2H": "FULL",
    "T_4H": "LIMITED",
    "T_12H": "WEAK",
    "T_24H_PLUS": "NONE",
}


def _apply_streak_permission(value: int, permission: str) -> int:
    """
    裁剪 streak，不做任何推断
    """
    if permission == "FULL":
        return value
    if permission == "LIMITED":
        return min(value, 1)
    if permission == "WEAK":
        return 1 if value >= 1 else 0
    return 0  # NONE


# =========================
# 核心风控决策函数
# =========================

def decide_position_action(
    *,
    holding_duration_min: int,
    time_since_last_event_min: int,
    valid_streak: int,
    invalid_streak: int,
    conflict_streak: int,
    risk_mode: str = "normal",  # normal | conservative | aggressive
) -> Dict[str, Any]:
    """
    Deterministic Position Risk Decision

    Returns:
        {
          "time_bucket": str,
          "allowed_actions": List[str],
          "veto_reasons": List[str],
          "effective_streak": Dict[str, int]
        }
    """

    # -------------------------
    # Step 0: 设定模式阈值
    # -------------------------
    # 默认 normal 模式
    streak_threshold_invalid = 2
    streak_threshold_conflict = 2
    streak_threshold_close = 3
    allow_expired_streak = False

    if risk_mode == "conservative":
        streak_threshold_invalid = 1  # 只要一次无效就 veto
        streak_threshold_conflict = 1
        streak_threshold_close = 2    # 两次无效就平仓
    elif risk_mode == "aggressive":
        streak_threshold_invalid = 3  # 允许连续两次无效
        streak_threshold_conflict = 3
        streak_threshold_close = 4
        allow_expired_streak = True   # 允许过期保留部分 streak

    # -------------------------
    # Step 1: 时间周期
    # -------------------------
    bucket = time_bucket(time_since_last_event_min)
    permission = STREAK_PERMISSION[bucket]

    # Aggressive 模式下，T_24H_PLUS 即使过期也给予 LIMITED 权限，防止被动平仓
    if allow_expired_streak and bucket == "T_24H_PLUS":
        permission = "LIMITED"

    # -------------------------
    # Step 2: streak 裁剪
    # -------------------------
    eff_valid = _apply_streak_permission(valid_streak, permission)
    eff_invalid = _apply_streak_permission(invalid_streak, permission)
    eff_conflict = _apply_streak_permission(conflict_streak, permission)

    allowed_actions: List[str] = []
    veto_reasons: List[str] = []

    # -------------------------
    # Step 3: 强否决规则
    # -------------------------
    if eff_invalid >= streak_threshold_invalid:
        veto_reasons.append("invalid_streak_high")
    if eff_conflict >= streak_threshold_conflict:
        veto_reasons.append("conflict_streak_high")
    if bucket == "T_24H_PLUS" and not allow_expired_streak:
        veto_reasons.append("temporal_memory_expired")

    # -------------------------
    # Step 4: ADD（加仓）
    # -------------------------
    if not veto_reasons:
        # 放宽：只要是有效验证，无论 streak 多少，都允许加仓尝试
        # 由 Agent 结合市场结构最终决定是否真的加
        if eff_valid >= 1:
            allowed_actions.append("ADD")
        
        # 即使没有 streak，如果是刚开始 (FULL/LIMITED) 且无坏账，也允许加仓
        elif permission in ["FULL", "LIMITED"] and eff_invalid == 0 and eff_conflict == 0:
            allowed_actions.append("ADD_CAUTIOUS")

    # -------------------------
    # Step 5: REDUCE（减仓）
    # -------------------------
    # 只有明确风险才强制减仓
    if eff_invalid >= streak_threshold_invalid:
        allowed_actions.append("REDUCE")
    elif eff_conflict >= streak_threshold_conflict:
        allowed_actions.append("REDUCE_OPTIONAL")
    
    # 默认允许 HOLD
    allowed_actions.append("HOLD")

    # -------------------------
    # Step 6: CLOSE（平仓）
    # -------------------------
    if invalid_streak >= streak_threshold_close:
        allowed_actions.append("CLOSE")
    elif invalid_streak >= (streak_threshold_close - 1) and holding_duration_min > 240:
        allowed_actions.append("CLOSE_OPTIONAL")

    # -------------------------
    # Step 7: HOLD（冻结）
    # -------------------------
    if eff_conflict >= streak_threshold_conflict:
        allowed_actions.append("HOLD_REDUCE_ONLY")
    elif bucket == "T_12H":
        allowed_actions.append("HOLD_NO_ADD")

    return {
        "time_bucket": bucket,
        "streak_permission": permission,
        "allowed_actions": sorted(set(allowed_actions)),
        "veto_reasons": veto_reasons,
        "effective_streak": {
            "valid": eff_valid,
            "invalid": eff_invalid,
            "conflict": eff_conflict,
        },
    }


if __name__ == "__main__":
    state = {"entry_ts": 1768045516478, "holding_duration_min": 1855, "last_verdict": "INVALID", "invalid_streak": 3, "conflict_streak": 0, "valid_streak": 0, "last_update_ts": 1768409722242}
    now_ts = time.time() * 1000
    # 基于 temporal state 做决策（不写回）
    decision = decide_position_action(
        holding_duration_min=state["holding_duration_min"],
        time_since_last_event_min=(
            now_ts - state["last_update_ts"]
        ) // 60_000,
        valid_streak=state["valid_streak"],
        invalid_streak=state["invalid_streak"],
        conflict_streak=state["conflict_streak"],
    )

    print(decision)