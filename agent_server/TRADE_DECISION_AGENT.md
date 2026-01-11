# 交易决策 Agent 使用说明

## 概述

交易决策 Agent 是多 Agent 系统的最后一个环节，负责综合信号验证结果、风控建议、L1 事件和市场结构，做出最终交易决策并执行。

## 工作流程

```
final_events Stream
    ↓
RouterFinalListener (final_listen_main.py)
    ↓ (route == "indicators")
SignalValidationWorkflow
    ↓
Step 1: SignalValidationComponent
    → SignalValidationExpert
    → 输出: verdict, direction
    ↓
Step 2: PositionRiskExecutionComponent
    → PositionRiskExpert
    → 输出: recommended_action, risk_state
    ↓
Step 3: TradeDecisionExecutionComponent (新增)
    → 读取 L1 事件 (l1_events stream)
    → 读取市场结构 (background:binance:{symbol}:market_structure)
    → 获取当前价格 (price:binance:{symbol})
    → TradeDecisionExpert
    → 输出: decision, order_type, quantity, tp/sl
    → 如果 should_execute==true，推送到 TASK_ADD_TRADE 队列
```

## 配置 PIPPINUSDT

**重要提示**：交易决策 Agent 的 symbol 是从 `final_events` 中的 `event_data.symbol` 动态获取的，**不是硬编码的**。只要 PIPPINUSDT 有 final_events 产生，Agent 就会处理它。

### 1. 添加监控币种（必需）

交易决策 Agent 只会处理已经在 Redis 中配置的监控币种。要处理 PIPPINUSDT，**必须先**将其添加到监控列表：

```bash
# 使用 redis-cli 添加 PIPPINUSDT
redis-cli SADD symbol:binance PIPPINUSDT

# 验证是否添加成功
redis-cli SMEMBERS symbol:binance
```

**注意**：如果 PIPPINUSDT 不在 `symbol:binance` 集合中，数据采集服务不会采集它的数据，也就不会有 final_events 产生，交易决策 Agent 也就不会处理它。

### 2. 确保数据采集服务运行

确保以下服务正在运行，以便为 PIPPINUSDT 采集数据：

- **data_server**: 采集 K 线、指标、市场数据
- **event_center**: 处理事件并生成 final_events

### 3. 确保背景数据生成

交易决策 Agent 需要以下背景数据：

- **market_structure**: `background:binance:PIPPINUSDT:market_structure`
- **market_state**: `background:binance:PIPPINUSDT:market_state`
- **L1 事件**: `l1_events` stream 中 PIPPINUSDT 的事件

确保 `agent_server/background_main.py` 正在运行，它会定期生成这些背景数据。

## 启动服务

### 1. 启动数据采集服务

```bash
# 启动 data_server (REST API 数据采集)
cd /Users/yb/my_project/utaker
python -m data_server.binance.rest_binance.app.main

# 启动 data_server (WebSocket 实时监听)
python -m data_server.binance.ws_binance.market_ws
```

### 2. 启动事件中心

```bash
# 启动 event_center
python -m event_center.main
```

### 3. 启动背景数据生成

```bash
# 启动 background_main (生成 market_structure 和 market_state)
python -m agent_server.background_main
```

### 4. 启动 Agent Server

```bash
# 启动 agent_server (包含交易决策 Agent)
python -m agent_server.final_listen_main
```

## 启动后应该看到的现象

### 1. 数据采集阶段

当 `data_server` 启动后，如果 PIPPINUSDT 已在 `symbol:binance` 集合中，你应该看到：

```
[SYMBOL WATCH] 新增订阅: {'PIPPINUSDT'}
```

### 2. 事件处理阶段

当 `event_center` 处理 PIPPINUSDT 的事件时，你应该看到：

```
[L0] 输出 event_id=binance.PIPPINUSDT.indicators.xxx 优先级=medium 信号=confirm
[L1] 输出 symbol=PIPPINUSDT 状态=momentum 方向=bullish 分数=56.9 优先级=medium
```

### 3. 背景数据生成阶段

当 `background_main` 生成 PIPPINUSDT 的背景数据时，你应该看到：

```
[Background] Processing binance PIPPINUSDT market_structure
[Background] Processing binance PIPPINUSDT market_state
```

### 4. Agent 处理阶段

当 `agent_server` 处理 PIPPINUSDT 的 final_event 时，你应该看到：

```
--- 信号验证：PIPPINUSDT ---
--- 持仓风控执行：PIPPINUSDT ---
--- 交易决策执行：PIPPINUSDT ---
  -> 读取 L1 事件成功
  -> 读取 market_structure 成功
  -> 获取当前价格: 0.12345
  -> TradeDecisionExpert 输出: {"decision": "OPEN_LONG", ...}
  -> 成功推送到交易队列: TASK_ADD_TRADE, 队列长度: 1
```

### 5. 交易决策输出示例

交易决策 Agent 的输出应该包含：

```json
{
  "decision": "OPEN_LONG",
  "order_type": "open",
  "order_type_binance": "MARKET",
  "symbol": "PIPPINUSDT",
  "position_side": "LONG",
  "side": "BUY",
  "leverage": 20.0,
  "margin": 200.0,
  "quantity": "32400",
  "limit_price": 0.0,
  "tp_trigger_px": 2.0,
  "sl_trigger_px": 1.0,
  "trade_trigger_mode": 1,
  "confidence": 0.85,
  "reasoning": [
    "信号验证 verdict=VALID，方向 bullish",
    "风控建议 risk_state=LOW，recommended_action=ADD_POSITION",
    "L1 事件 direction=bullish，与信号一致",
    "市场结构 cross_period_bias=long，支持做多"
  ],
  "should_execute": true,
  "trade_pushed": true
}
```

## 检查 PIPPINUSDT 是否已配置

### 1. 检查监控币种列表

```bash
redis-cli SMEMBERS symbol:binance
```

应该看到 `PIPPINUSDT` 在列表中。

### 2. 检查是否有 final_events

```bash
# 查看最新的 final_events
redis-cli XREVRANGE final_events + - COUNT 10

# 查找 PIPPINUSDT 的事件
redis-cli XREVRANGE final_events + - COUNT 100 | grep -i pippin
```

### 3. 检查背景数据

```bash
# 检查 market_structure
redis-cli GET "background:binance:PIPPINUSDT:market_structure"

# 检查 market_state
redis-cli GET "background:binance:PIPPINUSDT:market_state"

# 检查当前价格
redis-cli HGET "price:binance:PIPPINUSDT" "price"
```

### 4. 检查 L1 事件

```bash
# 查看最新的 L1 事件
redis-cli XREVRANGE l1_events + - COUNT 20

# 查找 PIPPINUSDT 的 L1 事件
redis-cli XREVRANGE l1_events + - COUNT 100 | grep -i pippin
```

## 常见问题

### Q1: 为什么看不到 PIPPINUSDT 的处理日志？

**A:** 可能的原因（按优先级排查）：

1. **PIPPINUSDT 未添加到 `symbol:binance` 集合**（最常见）
   - 解决：`redis-cli SADD symbol:binance PIPPINUSDT`
   - 验证：`redis-cli SMEMBERS symbol:binance` 应该包含 PIPPINUSDT

2. **没有生成 final_events**
   - 检查 `event_center` 是否正常运行
   - 检查是否有足够的市场数据触发事件
   - 验证：`redis-cli XREVRANGE final_events + - COUNT 10` 查看是否有 PIPPINUSDT 的事件

3. **final_events 的 route 不是 "indicators"**
   - 当前只处理 `route == "indicators"` 的事件
   - 其他 route（如 "trade"）不会触发交易决策 Agent

4. **没有背景数据**
   - 检查 `background:binance:PIPPINUSDT:market_structure` 是否存在
   - 检查 `background:binance:PIPPINUSDT:market_state` 是否存在
   - 确保 `agent_server/background_main.py` 正在运行

### Q2: 为什么交易决策是 NO_ACTION？

**A:** 可能的原因：
1. 信号验证 verdict=INVALID
2. 风控建议 recommended_action=HOLD
3. L1 事件方向与信号验证方向不一致
4. 市场结构不支持当前交易方向
5. 无法获取当前价格

### Q3: 为什么交易订单没有推送到队列？

**A:** 可能的原因：
1. `should_execute=false`
2. `decision` 不是 OPEN_LONG/OPEN_SHORT/CLOSE/REDUCE
3. 无法构建交易 JSON（缺少必要参数）
4. Redis 连接失败（检查交易队列的 Redis 配置）

### Q4: 如何修改默认保证金和杠杆？

**A:** 在 `trade_decision_execution.py` 的 `execute` 方法中修改：

```python
query = {
    ...
    "default_margin": 200.0,  # 修改这里
    "default_leverage": 20.0  # 修改这里
}
```

或者让 Agent 根据市场情况自动决定（需要在 prompt 中说明）。

## 配置说明

### 交易队列配置

当前交易队列配置硬编码在 `trade_decision_execution.py` 中：

```python
self.trade_redis_config = {
    'host': '38.147.173.111',
    'port': 6379,
    'password': '112233Ww..',
    'db': 8,
    'decode_responses': False
}
self.trade_queue_name = 'TASK_ADD_TRADE'
```

### API 密钥配置

当前 API 密钥为空，需要在推送交易前配置：

```python
"acc": {
    "key": "",  # 需要配置
    "secret": "",  # 需要配置
    ...
}
```

### 默认参数

- **保证金**: 200 USDT
- **杠杆**: 20 倍
- **交易类型**: 市价单 (MARKET)
- **标志**: 模拟盘 (flag="1")

## 测试建议

1. **先测试数据采集**：确保 PIPPINUSDT 的数据正常采集
2. **再测试事件生成**：确保有 final_events 产生
3. **最后测试交易决策**：观察 Agent 的决策逻辑和输出

## 下一步优化

1. 从环境变量读取交易队列配置
2. 从配置文件读取 API 密钥
3. 支持平仓/减仓时的数量计算（需要从持仓获取）
4. 根据市场波动率自动调整止盈止损
5. 支持限价单的限价计算（根据支撑/阻力位）

