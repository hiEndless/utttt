# AI 分析脚本使用说明

## 脚本功能

`run_ai_analysis.py` 是一个 AI 分析脚本，用于：
1. 从事件中心（Redis Streams）读取事件
2. 调用 Agent 系统进行智能分析
3. 返回格式化的分析结果
4. 保存分析结果到文件

## 使用方法

### 基本用法

#### 1. 运行一次分析（默认模式）

```bash
# 从 final_events 流读取一个事件并分析
python run_ai_analysis.py

# 或者明确指定
python run_ai_analysis.py --mode once --stream final_events
```

#### 2. 持续运行模式

```bash
# 持续监听事件流，每10秒检查一次
python run_ai_analysis.py --mode continuous

# 自定义检查间隔（秒）
python run_ai_analysis.py --mode continuous --interval 5
```

#### 3. 监听不同的事件流

```bash
# 监听原始事件流
python run_ai_analysis.py --stream raw_event_stream

# 监听 L0 级别事件
python run_ai_analysis.py --stream l0_events

# 监听 L1 级别事件
python run_ai_analysis.py --stream l1_events

# 监听最终事件流（推荐，只分析重要事件）
python run_ai_analysis.py --stream final_events
```

### 完整参数说明

```bash
python run_ai_analysis.py [选项]

选项:
  --stream STREAM    要监听的事件流
                     可选值: raw_event_stream, l0_events, l1_events, final_events
                     默认: final_events

  --mode MODE        运行模式
                     once: 运行一次（读取一个事件并分析）
                     continuous: 持续运行（持续监听新事件）
                     默认: once

  --interval INTERVAL 持续模式下的检查间隔（秒）
                     默认: 10
```

## 输出说明

### 控制台输出

脚本会在控制台输出：
1. **事件信息**: 读取到的事件详情
2. **AI 分析过程**: 参与分析的 Agent 列表
3. **各 Agent 输出**: 每个 Agent 的分析结果
4. **评分和权重**: 自动评分和权重分布
5. **融合结果**: 最终融合后的分析结果
6. **反思评分**: Agent 输出的质量评分

### 文件输出

分析结果会自动保存到 `results/` 目录下，文件名格式：
```
analysis_result_YYYYMMDD_HHMMSS.json
```

文件包含完整的分析结果，包括：
- 原始事件数据
- 各 Agent 的输出
- 评分和权重
- 融合结果
- 反思结果

## 环境变量配置

脚本会从环境变量读取 Redis 配置：

```bash
export REDIS_HOST="38.147.173.111"
export REDIS_PORT="6379"
export REDIS_PASSWORD="112233Ww.."
export REDIS_DB="8"
```

如果没有设置环境变量，脚本会使用默认值。

## 使用示例

### 示例 1: 快速分析一个事件

```bash
python run_ai_analysis.py --mode once --stream final_events
```

输出：
```
✅ Redis 连接成功: 38.147.173.111:6379/8

📥 读取到事件:
   事件ID: BTCUSDT.combo.15m.rsi_kdj_combo.rsi_kdj_bullish.1766112469336
   事件类型: combo.15m.rsi_kdj_combo.rsi_kdj_bullish
   交易对: BTCUSDT
   事件级别: 2

============================================================
开始 AI 分析...
事件类型: market_signal
事件强度: low
交易对: BTCUSDT
============================================================

================================================================================
AI 分析结果 - 2025-12-19 11:00:00
================================================================================

参与分析的 Agent: technical, risk

────────────────────────────────────────────────────────────────────────────────
Agent: technical
────────────────────────────────────────────────────────────────────────────────
{
  "action": "buy",
  "confidence": 0.75,
  ...
}

...
```

### 示例 2: 持续监听重要事件

```bash
python run_ai_analysis.py --mode continuous --stream final_events --interval 5
```

这会持续运行，每5秒检查一次 `final_events` 流中的新事件，一旦有新事件就会自动分析。

### 示例 3: 分析所有事件

```bash
python run_ai_analysis.py --mode continuous --stream raw_event_stream --interval 3
```

这会监听原始事件流，分析所有事件（包括低级别事件）。

## 注意事项

1. **事件流选择**:
   - `final_events`: 只包含重要事件（level >= 4），推荐使用
   - `l1_events`: 包含高优先级事件（level = 3）
   - `l0_events`: 包含所有技术指标事件（level < 3）
   - `raw_event_stream`: 包含所有原始事件

2. **运行模式**:
   - `once`: 适合测试和单次分析
   - `continuous`: 适合生产环境，持续监控

3. **检查间隔**:
   - 建议设置为 5-10 秒
   - 太短会增加 Redis 连接压力
   - 太长可能错过事件

4. **Agent 系统要求**:
   - 确保 Agent 系统配置正确（LLM API 密钥等）
   - 确保事件中心正在运行并产生事件

5. **结果保存**:
   - 结果会自动保存到 `results/` 目录
   - 建议定期清理旧的结果文件

## 故障排查

### 问题 1: Redis 连接失败

```
❌ Redis 连接失败: ...
```

**解决方案**:
- 检查 Redis 服务器是否运行
- 检查网络连接
- 验证 Redis 密码和端口

### 问题 2: 未读取到事件

```
⚠️  未读取到新事件（流: final_events）
```

**解决方案**:
- 检查事件中心是否正在运行
- 检查指定的事件流是否有数据
- 尝试监听其他事件流（如 `raw_event_stream`）

### 问题 3: AI 分析失败

```
❌ AI 分析失败: ...
```

**解决方案**:
- 检查 Agent 系统配置
- 检查 LLM API 密钥是否正确
- 查看详细错误信息

### 问题 4: 导入错误

```
ModuleNotFoundError: No module named 'agent_server'
```

**解决方案**:
- 确保在项目根目录运行脚本
- 检查 Python 路径配置

## 集成到交易系统

脚本返回的结果可以用于：

1. **提取交易信号**:
   ```python
   result = await analyzer.run_once("final_events")
   trading_signal = extract_trading_signal(result)
   ```

2. **执行交易**:
   ```python
   if trading_signal["action"] == "buy":
       await execute_buy_order(trading_signal)
   ```

3. **风险控制**:
   ```python
   if trading_signal["confidence"] > 0.8:
       # 高置信度，执行交易
   ```

## 相关文件

- 脚本: `run_ai_analysis.py`
- Agent 系统文档: `Agent系统文档.md`
- 结果保存目录: `results/`

