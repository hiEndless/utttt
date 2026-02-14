"""
agent_server.internal_api

为内部后端服务提供“手动触发 / 调试调用”入口：
- 刷新 K 线背景（写入 Redis background:{exchange}:{symbol}:{interval}）
- 刷新市场结构背景（写入 Redis background:{exchange}:{symbol}:market_state）
- 运行工作流（signal_validation / trade_event）
"""

