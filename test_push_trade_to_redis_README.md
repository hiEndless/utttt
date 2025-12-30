# 交易推送测试脚本使用说明

## 📋 简介

`test_push_trade_to_redis.py` 是一个用于测试推送交易订单到 Redis 队列的脚本，包含 4 个完整的交易示例。

## 🚀 快速开始

### 1. 基本使用

```bash
# 交互式选择示例
python test_push_trade_to_redis.py

# 直接指定示例编号
python test_push_trade_to_redis.py 1    # 开多
python test_push_trade_to_redis.py 2    # 平多
python test_push_trade_to_redis.py 3    # 开空
python test_push_trade_to_redis.py 4    # 平空
python test_push_trade_to_redis.py 5    # 查看所有示例 JSON（不推送）
```

### 2. 交易示例说明

| 示例 | 操作 | order_type | positionSide | side | 说明 |
|------|------|------------|--------------|------|------|
| 1 | 开多 | `open` | `LONG` | `BUY` | 买入开多仓 |
| 2 | 平多 | `close` | `LONG` | `SELL` | 卖出平多仓 |
| 3 | 开空 | `open` | `SHORT` | `SELL` | 卖出开空仓 |
| 4 | 平空 | `close` | `SHORT` | `BUY` | 买入平空仓 |

## ⚙️ 配置参数

### 默认参数

脚本默认使用以下参数（可在代码中修改）：

```python
DEFAULT_SYMBOL = 'RVVUSDT'      # 交易对
DEFAULT_PRICE = 0.005411         # 价格
DEFAULT_AMOUNT = '0.1'          # 数量
DEFAULT_LEVERAGE = 5.0           # 杠杆
DEFAULT_TASK_ID = 766            # 任务ID
DEFAULT_USER_ID = 2              # 用户ID
DEFAULT_API_ID = 0               # API ID
```

### 通过环境变量自定义

**Windows PowerShell:**

```powershell
$env:TEST_SYMBOL="RVVUSDT"          # 交易对
$env:TEST_PRICE="0.005411"           # 价格
$env:TEST_AMOUNT="0.1"               # 数量
$env:TEST_LEVERAGE="5.0"             # 杠杆
$env:TEST_TASK_ID="766"              # 任务ID
$env:TEST_USER_ID="2"                # 用户ID
$env:TEST_API_ID="0"                 # API ID
```

**Linux/Mac:**

```bash
export TEST_SYMBOL="RVVUSDT"
export TEST_PRICE="0.005411"
export TEST_AMOUNT="0.1"
export TEST_LEVERAGE="5.0"
export TEST_TASK_ID="766"
export TEST_USER_ID="2"
export TEST_API_ID="0"
```

### Redis 配置

**Windows PowerShell:**

```powershell
$env:TRADE_REDIS_HOST="101.32.115.249"
$env:TRADE_REDIS_PORT="6379"
$env:TRADE_REDIS_PASSWORD="liu146015"
$env:TRADE_REDIS_DB="1"
$env:TRADE_TASK_KEY="TASK_ADD_TRADE"
```

**Linux/Mac:**

```bash
export TRADE_REDIS_HOST="101.32.115.249"
export TRADE_REDIS_PORT="6379"
export TRADE_REDIS_PASSWORD="liu146015"
export TRADE_REDIS_DB="1"
export TRADE_TASK_KEY="TASK_ADD_TRADE"
```

## 📝 使用示例

### 示例 1: 测试开多订单

```bash
python test_push_trade_to_redis.py 1
```

输出示例：
```
🚀 测试推送交易 JSON 到 Redis
   Redis: 101.32.115.249:6379
   队列: TASK_ADD_TRADE
   交易对: RVVUSDT
   价格: 0.005411
   数量: 0.1
   杠杆: 5.0x

============================================================
📋 示例1: 开多（LONG）
============================================================
订单类型: open
交易对: RVVUSDT
持仓方向: LONG
交易方向: BUY
杠杆: 5.0
数量: 0.1
开仓价格: 0.005411
止损价格: 0.005303
止盈价格: 0.005682
任务ID: 766
用户ID: 2
API ID: 0
标志: 1 (0=实盘, 1=模拟盘)
============================================================

⚠️  准备推送到 Redis 队列...
   按 Enter 继续，或 Ctrl+C 取消
```

### 示例 2: 查看所有示例 JSON

```bash
python test_push_trade_to_redis.py 5
```

这会显示所有 4 个示例的完整 JSON 结构，但不会推送到 Redis。

## 🔍 验证推送结果

### 使用 Redis CLI 检查队列

```bash
redis-cli -h 101.32.115.249 -p 6379 -a liu146015 LLEN TASK_ADD_TRADE
```

### 查看队列中的订单

```bash
redis-cli -h 101.32.115.249 -p 6379 -a liu146015 LRANGE TASK_ADD_TRADE 0 -1
```

## ⚠️ 注意事项

1. **模拟盘 vs 实盘**
   - `flag="1"` 表示模拟盘
   - `flag="0"` 表示实盘
   - 默认使用模拟盘，请谨慎修改

2. **数据格式**
   - `sums` 字段必须是字符串类型
   - `positionSide` 和 `side` 必须大写
   - `symbol` 不能包含分隔符（如 `ETH-USDT` 应改为 `ETHUSDT`）

3. **止损止盈**
   - 开多：止损在价格下方，止盈在价格上方
   - 开空：止损在价格上方，止盈在价格下方
   - 平仓订单不需要止损止盈

4. **API 配置**
   - 默认 `api_key`、`api_secret`、`api_passphrase` 为空
   - 如需实盘测试，请通过环境变量或代码设置

## 📚 相关文档

- `BINANCE_TRADE_JSON_GUIDE.md` - 币安交易 JSON 格式详细说明
- `redis_push_json_example.json` - Redis 推送 JSON 示例

## 🐛 常见问题

### Q: Redis 连接失败怎么办？

A: 检查以下配置：
- Redis 主机地址和端口
- Redis 密码
- 网络连接是否正常

### Q: 如何修改交易对和价格？

A: 有两种方式：
1. 修改代码中的默认值
2. 通过环境变量设置（推荐）

### Q: 如何查看推送的 JSON 内容？

A: 使用示例 5 查看所有 JSON，或使用 Redis CLI 查看队列内容。

## 📞 支持

如有问题，请检查：
1. Redis 连接配置
2. 交易参数是否正确
3. JSON 格式是否符合币安要求

