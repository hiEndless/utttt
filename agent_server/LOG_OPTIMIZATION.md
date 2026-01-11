# 日志优化说明

## 优化内容

### 1. 减少日志噪音

已将所有非关键警告改为 DEBUG 级别，包括：

- **数据库警告**：数据库连接池懒加载是正常的，不再显示警告
- **价格数据警告**：价格数据可能暂时缺失，改为 DEBUG
- **事件记录器警告**：事件不存在等正常情况，改为 DEBUG
- **agno 框架日志**：设置为 ERROR，只显示错误

### 2. 独立的 Trade 日志系统

**日志文件位置**：`agent_server/logs/trade_decision_YYYYMMDD.log`

所有交易决策相关的日志都记录到独立文件，包括：
- L1 事件接收
- 工作流启动和完成
- 信号验证结果
- 风控建议
- 交易决策结果
- 订单推送状态

### 3. 控制台输出优化

控制台现在只显示：
- Trade Listener 的启动信息
- Trade 决策的关键步骤（通过 `[TRADE]` 前缀）
- 错误信息

不再显示：
- DEBUG 级别的日志
- agno 框架的调试信息
- 数据库、价格、事件记录器的正常警告

## 启动后应该看到的现象

### 启动时

```
[Main] 启动 Trade Decision Agent
[Main] 目标币种: PIPPINUSDT
[Main] 日志目录: /Users/yb/my_project/utaker/agent_server/logs

============================================================
[TradeListener] 启动成功
  监听流: l1_events
  目标币种: PIPPINUSDT
  日志文件: .../logs/trade_decision_20250115.log
============================================================

[TRADE] === Trade L1 Listener 启动 ===
[TRADE] 监听流: l1_events
[TRADE] 目标币种: PIPPINUSDT
[TRADE] 开始监听 l1_events stream...
```

### 处理事件时

```
[TRADE] 收到L1事件 | PIPPINUSDT | direction=bullish | score=56.9 | priority=medium
[TRADE] 触发工作流 | PIPPINUSDT | event_id=... | direction=bullish | score=56.9
[TRADE] === 交易决策开始 === | PIPPINUSDT | ...
[TRADE] 当前价格 | PIPPINUSDT | 0.12345
[TRADE] L1事件 | PIPPINUSDT | direction=bullish | score=56.9
[TRADE] 市场结构 | PIPPINUSDT | bias=long | alignment=0.79
[TRADE] 信号验证结果 | PIPPINUSDT | verdict=VALID | direction=bullish
[TRADE] 风控建议 | PIPPINUSDT | risk_state=LOW | action=ADD_POSITION
[TRADE] 调用TradeDecisionExpert | PIPPINUSDT | ...
[TRADE] 交易决策结果 | PIPPINUSDT | decision=OPEN_LONG | should_execute=true | confidence=0.85
[TRADE] 交易订单已推送 | PIPPINUSDT | OPEN_LONG | quantity=32400 | price=0.12345
[TRADE] === 交易决策完成 === | PIPPINUSDT | ... | decision=OPEN_LONG
[TRADE] 工作流完成 | PIPPINUSDT | event_id=... | decision=OPEN_LONG | should_execute=true
```

## 查看日志

### 实时查看日志文件

```bash
# 查看今天的日志
tail -f agent_server/logs/trade_decision_$(date +%Y%m%d).log

# 或者直接指定日期
tail -f agent_server/logs/trade_decision_20250115.log
```

### 查看 Redis 中的分析过程

```bash
# 查看今天的分析过程（最近 10 条）
redis-cli LRANGE trade:analysis:PIPPINUSDT:$(date +%Y%m%d) 0 9

# 查看今天的决策结果（最近 10 条）
redis-cli LRANGE trade:decision:PIPPINUSDT:$(date +%Y%m%d) 0 9
```

## 常见问题

### Q1: 为什么看不到交易决策日志？

**A:** 可能的原因：
1. 没有 L1 事件产生（检查 `event_center` 是否运行）
2. L1 事件中的 symbol 不是 PIPPINUSDT（检查事件内容）
3. 价格数据缺失，导致交易决策提前退出

### Q2: 为什么价格数据缺失？

**A:** 价格数据由 `data_server` 采集，确保：
1. `data_server` 正在运行
2. PIPPINUSDT 在 `symbol:binance` 集合中
3. WebSocket 连接正常

### Q3: 如何查看完整的分析过程？

**A:** 
1. 查看日志文件：`agent_server/logs/trade_decision_YYYYMMDD.log`
2. 查看 Redis：`trade:analysis:PIPPINUSDT:YYYYMMDD` 和 `trade:decision:PIPPINUSDT:YYYYMMDD`

## 日志级别说明

- **ERROR**: 真正的错误，需要关注
- **WARNING**: 已优化为 DEBUG，不再显示
- **INFO**: Trade 决策的关键步骤（控制台和文件都显示）
- **DEBUG**: 详细的调试信息（只在日志文件中）

## 下一步

如果还需要进一步优化，可以：
1. 添加日志轮转（避免日志文件过大）
2. 添加日志压缩（自动压缩旧日志）
3. 添加日志查询接口（通过 API 查询历史日志）

