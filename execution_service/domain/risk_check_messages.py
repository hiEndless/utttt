from __future__ import annotations

# 中文注释：统一 risk_checks.message_zh 文案模板，避免不同规则输出格式漂移。
RISK_MSG_ACCOUNT_DRAWDOWN = "账户回撤检查: 当前={value:.4f}, 阈值={threshold:.4f}"
RISK_MSG_ACCOUNT_AVAILABLE_BALANCE = "可用余额检查: 当前={value:.4f}, 阈值={threshold:.4f}"
RISK_MSG_ACCOUNT_NOTIONAL_LIMIT = "账户总敞口检查: 当前={value:.4f}, 阈值={threshold:.4f}"
RISK_MSG_ACCOUNT_MARGIN_RATIO_LIMIT = "账户保证金率检查: 当前={value:.4f}, 阈值={threshold:.4f}"
RISK_MSG_ACCOUNT_DAILY_LOSS_LIMIT = "账户当日亏损检查: 当前={value:.4f}, 阈值={threshold:.4f}"
RISK_MSG_ACCOUNT_CONSECUTIVE_LOSS_LIMIT = "账户连续亏损次数检查: 当前={value:.0f}, 阈值={threshold:.0f}"
RISK_MSG_SYMBOL_EXPOSURE_RATIO = "symbol 暴露占比检查: 当前={value:.4f}, 阈值={threshold:.4f}"
RISK_MSG_LONG_LEG_POSITION_LIMIT = "多头仓位上限检查: 当前={value:.4f}, 阈值={threshold:.4f}"
RISK_MSG_SHORT_LEG_POSITION_LIMIT = "空头仓位上限检查: 当前={value:.4f}, 阈值={threshold:.4f}"
