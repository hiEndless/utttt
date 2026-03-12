from __future__ import annotations

# 中文注释：risk_state 单点定义，避免 provider/规则与 schema 漂移。
RISK_STATE_NORMAL = "normal"
RISK_STATE_WARN = "warn"
RISK_STATE_REDUCE_ONLY = "reduce_only"
RISK_STATE_FROZEN = "frozen"

RISK_STATES = (
    RISK_STATE_NORMAL,
    RISK_STATE_WARN,
    RISK_STATE_REDUCE_ONLY,
    RISK_STATE_FROZEN,
)

