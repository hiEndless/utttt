# Trade Listener 更新说明

## 更新内容

### 1. 新增直接监听 L1 事件的监听器

**文件**: `agent_server/trade_listen_main.py`

- 直接监听 `l1_events` stream，不再依赖 `final_events`
- 自动过滤指定币种（默认 PIPPINUSDT，可通过环境变量 `TRADE_SYMBOL` 配置）
- 只处理目标币种的事件，减少不必要的处理

### 2. 独立的 Trade 日志系统

**日志文件位置**: `agent_server/logs/trade_decision_YYYYMMDD.log`

- 所有交易决策相关的日志都记录到独立文件
- 日志格式：`时间戳 [TRADE] 事件类型 | 币种 | 详细信息`
- 不会与其他服务的日志混在一起

### 3. Redis 存储分析过程

所有分析过程都会存储到 Redis：

- **分析过程**: `trade:analysis:{symbol}:{YYYYMMDD}` (List，保留最近 1000 条)
- **决策结果**: `trade:decision:{symbol}:{YYYYMMDD}` (List，保留最近 1000 条)
- 数据保留 7 天

### 4. 优化的日志输出

- 减少了控制台日志的噪音（httpx, httpcore, agno 等 logger 设置为 WARNING）
- 只显示关键的 trade 决策信息
- 详细的日志记录到文件

## 使用方法

### 启动服务

```bash
# 默认监听 PIPPINUSDT
python -m agent_server.main

# 或者指定其他币种
TRADE_SYMBOL=BTCUSDT python -m agent_server.main
```

### 查看日志

```bash
# 实时查看 trade 日志
tail -f agent_server/logs/trade_decision_$(date +%Y%m%d).log

# 或者查看今天的日志
cat agent_server/logs/trade_decision_$(date +%Y%m%d).log
```

### 查看 Redis 中的分析过程

```bash
# 查看今天的分析过程（最近 10 条）
redis-cli LRANGE trade:analysis:PIPPINUSDT:$(date +%Y%m%d) 0 9

# 查看今天的决策结果（最近 10 条）
redis-cli LRANGE trade:decision:PIPPINUSDT:$(date +%Y%m%d) 0 9
```

## 日志示例

### 日志文件内容示例

```
2025-01-15 10:30:15 [TRADE] === Trade L1 Listener 启动 ===
2025-01-15 10:30:15 [TRADE] 监听流: l1_events
2025-01-15 10:30:15 [TRADE] 目标币种: PIPPINUSDT
2025-01-15 10:30:20 [TRADE] L1_EVENT_RECEIVED | PIPPINUSDT | {"entry_id":"...","direction":"bullish","total_score":56.9}
2025-01-15 10:30:20 [TRADE] TRADE_WORKFLOW_START | PIPPINUSDT | {"event_id":"...","direction":"bullish"}
2025-01-15 10:30:25 [TRADE] === 交易决策开始 === | PIPPINUSDT | binance.PIPPINUSDT.indicators.xxx
2025-01-15 10:30:25 [TRADE] 当前价格 | PIPPINUSDT | 0.12345
2025-01-15 10:30:25 [TRADE] L1事件 | PIPPINUSDT | direction=bullish | score=56.9
2025-01-15 10:30:25 [TRADE] 市场结构 | PIPPINUSDT | bias=long | alignment=0.79
2025-01-15 10:30:25 [TRADE] 信号验证结果 | PIPPINUSDT | verdict=VALID | direction=bullish
2025-01-15 10:30:25 [TRADE] 风控建议 | PIPPINUSDT | risk_state=LOW | action=ADD_POSITION
2025-01-15 10:30:30 [TRADE] 交易决策结果 | PIPPINUSDT | decision=OPEN_LONG | should_execute=true | confidence=0.85
2025-01-15 10:30:30 [TRADE] 交易订单已推送 | PIPPINUSDT | OPEN_LONG | quantity=32400 | price=0.12345
2025-01-15 10:30:30 [TRADE] === 交易决策完成 === | PIPPINUSDT | binance.PIPPINUSDT.indicators.xxx | decision=OPEN_LONG
```

## 配置说明

### 环境变量

- `TRADE_SYMBOL`: 要监听的币种（默认: PIPPINUSDT）

### 日志配置

日志文件会自动按日期创建，格式：`trade_decision_YYYYMMDD.log`

## 工作流程

1. **监听 L1 事件**: `trade_listen_main.py` 监听 `l1_events` stream
2. **过滤币种**: 只处理 `TRADE_SYMBOL` 指定币种的事件
3. **触发工作流**: 将 L1 事件转换为 final_event 格式，触发 `SignalValidationWorkflow`
4. **记录日志**: 每个步骤都记录到日志文件和 Redis
5. **执行决策**: 如果 `should_execute==true`，推送到 `TASK_ADD_TRADE` 队列

## 注意事项

1. 确保 PIPPINUSDT 已添加到 `symbol:binance` 集合
2. 确保 `event_center` 正在运行，以便生成 L1 事件
3. 确保 `agent_server/background_main.py` 正在运行，以便生成背景数据
4. 日志文件会自动创建，无需手动创建目录

