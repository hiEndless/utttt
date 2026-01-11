# 交易服务 API 文档

## 目录

- [概述](#概述)
- [Redis 配置](#redis-配置)
- [市价单交易](#市价单交易)
- [限价单交易](#限价单交易)
- [字段说明](#字段说明)
- [操作示例](#操作示例)
- [注意事项](#注意事项)

---

## 概述

交易服务通过 Redis 队列接收交易指令，支持币安（Binance）期货的市价单和限价单交易。

### 支持的功能

- ✅ 市价单开仓/平仓（开多、开空、平多、平空）
- ✅ 限价单开仓/平仓（开多、开空、平多、平空）
- ✅ 止盈止损设置（市价单：百分比模式；限价单：价格模式）
- ✅ 自动清理孤儿订单
- ✅ 支持实盘和模拟盘

### 交易类型

| 订单类型 | order_type | order_type_binance | 说明 |
|---------|-----------|-------------------|------|
| 市价单 | open/close/reduce | MARKET | 立即按市价成交 |
| 限价单 | open/close/reduce | LIMIT | 按指定价格成交 |

---

## Redis 配置

### 连接信息

```python
REDIS_CONFIG = {
    'host': '38.147.173.111',
    'port': 6379,
    'password': '112233Ww..',
    'db': 8,
    'encoding': 'utf-8',
    'decode_responses': False  # 使用 bytes 模式
}
```

### 队列名称

- **队列Key**: `TASK_ADD_TRADE`
- **操作**: 使用 `LPUSH` 推送消息
- **消费**: 交易服务使用 `BRPOP` 阻塞消费

---

## 市价单交易

### 特点

- 立即按当前市价成交
- 止盈止损使用**百分比模式**（相对开仓价格）
- 开仓后立即设置止盈止损

### JSON 结构

```json
{
  "order_type": "open",
  "symbol": "POLUSDT",
  "positionSide": "LONG",
  "side": "BUY",
  "leverage": 20.0,
  "sums": "10000",
  "openAvgPx": 0.16739,
  "task_id": 23,
  "user_id": 2,
  "api_id": 0,
  "trade_trigger_mode": 1,
  "tp_trigger_px": 60.0,
  "sl_trigger_px": 50.0,
  "acc": {
    "key": "",
    "secret": "",
    "passphrase": "",
    "proxies": {},
    "exchange": 2
  },
  "flag": "1",
  "uniqueName": "ai_trading_system"
}
```

### 关键字段说明（市价单）

| 字段 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `order_type` | string | ✅ | `"open"`（开仓）/ `"close"`（平仓）/ `"reduce"`（减仓） |
| `order_type_binance` | string | ❌ | 市价单不需要，系统自动识别为 MARKET |
| `symbol` | string | ✅ | 交易对，如 `"POLUSDT"` |
| `positionSide` | string | ✅ | `"LONG"`（多）或 `"SHORT"`（空） |
| `side` | string | ✅ | `"BUY"`（买入）或 `"SELL"`（卖出） |
| `leverage` | float | ✅ | 杠杆倍数，如 `20.0` |
| `sums` | string | ✅ | 交易数量（字符串），需符合币安精度 |
| `openAvgPx` | float | ✅ | 参考价格（用于计算名义价值，实际成交价按市价） |
| `trade_trigger_mode` | int | ✅ | `0`=关闭止盈止损，`1`=开启 |
| `tp_trigger_px` | float | ⚠️ | **百分比**，如 `60.0` 表示60%（仅在 `trade_trigger_mode=1` 时有效） |
| `sl_trigger_px` | float | ⚠️ | **百分比**，如 `50.0` 表示50%（仅在 `trade_trigger_mode=1` 时有效） |

---

## 限价单交易

### 特点

- 按指定价格成交（需达到限价才成交）
- 止盈止损使用**价格模式**（具体价格，不是百分比）
- 限价单提交后立即设置止盈止损条件单

### JSON 结构

```json
{
  "order_type": "open",
  "symbol": "POLUSDT",
  "positionSide": "LONG",
  "side": "BUY",
  "leverage": 20.0,
  "sums": "10000",
  "openAvgPx": 0.17655,
  "limit_price": 0.17655,
  "order_type_binance": "LIMIT",
  "timeInForce": "GTC",
  "task_id": 23,
  "user_id": 2,
  "api_id": 0,
  "trade_trigger_mode": 1,
  "tp_trigger_px": 0.28248,
  "sl_trigger_px": 0.083695,
  "acc": {
    "key": "",
    "secret": "",
    "passphrase": "",
    "proxies": {},
    "exchange": 2
  },
  "flag": "1",
  "uniqueName": "ai_trading_system"
}
```

### 关键字段说明（限价单）

| 字段 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `order_type` | string | ✅ | `"open"`（开仓）/ `"close"`（平仓）/ `"reduce"`（减仓） |
| `order_type_binance` | string | ✅ | 限价单必须为 `"LIMIT"` |
| `limit_price` | float | ✅ | 限价价格（必须符合币安 tickSize 精度） |
| `timeInForce` | string | ✅ | `"GTC"`（Good Till Cancel，直到取消） |
| `symbol` | string | ✅ | 交易对，如 `"POLUSDT"` |
| `positionSide` | string | ✅ | `"LONG"`（多）或 `"SHORT"`（空） |
| `side` | string | ✅ | `"BUY"`（买入）或 `"SELL"`（卖出） |
| `leverage` | float | ✅ | 杠杆倍数，如 `20.0` |
| `sums` | string | ✅ | 交易数量（字符串），需符合币安精度 |
| `openAvgPx` | float | ✅ | 参考价格（通常等于 `limit_price`） |
| `trade_trigger_mode` | int | ✅ | `0`=关闭止盈止损，`1`=开启 |
| `tp_trigger_px` | float | ⚠️ | **具体价格**，如 `0.28248`（仅在 `trade_trigger_mode=1` 时有效） |
| `sl_trigger_px` | float | ⚠️ | **具体价格**，如 `0.083695`（仅在 `trade_trigger_mode=1` 时有效） |

---

## 字段说明

### 核心交易字段

| 字段 | 类型 | 必填 | 说明 | 示例 |
|-----|------|------|------|------|
| `order_type` | string | ✅ | 订单类型：`"open"`（开仓）、`"close"`（平仓）、`"reduce"`（减仓） | `"open"` |
| `symbol` | string | ✅ | 交易对（币安合约） | `"POLUSDT"` |
| `positionSide` | string | ✅ | 持仓方向：`"LONG"`（多）、`"SHORT"`（空） | `"LONG"` |
| `side` | string | ✅ | 交易方向：`"BUY"`（买入）、`"SELL"`（卖出） | `"BUY"` |
| `leverage` | float | ✅ | 杠杆倍数 | `20.0` |
| `sums` | string | ✅ | 交易数量（字符串格式，需符合币安精度） | `"10000"` |
| `openAvgPx` | float | ✅ | 参考价格（市价单用于计算名义价值，限价单通常等于限价） | `0.17655` |

### 限价单专用字段

| 字段 | 类型 | 必填 | 说明 | 示例 |
|-----|------|------|------|------|
| `order_type_binance` | string | ✅ | 必须为 `"LIMIT"` | `"LIMIT"` |
| `limit_price` | float | ✅ | 限价价格（需符合币安 tickSize 精度） | `0.17655` |
| `timeInForce` | string | ✅ | 有效期：`"GTC"`（直到取消） | `"GTC"` |

### 止盈止损字段

| 字段 | 类型 | 必填 | 说明 | 市价单示例 | 限价单示例 |
|-----|------|------|------|-----------|-----------|
| `trade_trigger_mode` | int | ✅ | `0`=关闭，`1`=开启 | `1` | `1` |
| `tp_trigger_px` | float | ⚠️ | 止盈价格/比例 | `60.0`（60%百分比） | `0.28248`（具体价格） |
| `sl_trigger_px` | float | ⚠️ | 止损价格/比例 | `50.0`（50%百分比） | `0.083695`（具体价格） |

**注意**：
- **市价单**：`tp_trigger_px` 和 `sl_trigger_px` 使用**百分比**（如 `5.0` 表示5%）
- **限价单**：`tp_trigger_px` 和 `sl_trigger_px` 使用**具体价格**（如 `0.28248`）

### 账户标识字段

| 字段 | 类型 | 必填 | 说明 | 示例 |
|-----|------|------|------|------|
| `task_id` | int | ✅ | 任务ID | `23` |
| `user_id` | int | ✅ | 用户ID | `2` |
| `api_id` | int | ✅ | API ID | `0` |
| `flag` | string | ✅ | `"0"`=实盘，`"1"`=模拟盘 | `"1"` |
| `acc` | object | ✅ | 账户信息对象 | 见下方 |

### 账户信息对象（acc）

```json
{
  "key": "your_api_key",
  "secret": "your_api_secret",
  "passphrase": "",
  "proxies": {},
  "exchange": 2
}
```

| 字段 | 类型 | 必填 | 说明 | 示例 |
|-----|------|------|------|------|
| `key` | string | ✅ | API Key | `"your_api_key"` |
| `secret` | string | ✅ | API Secret | `"your_api_secret"` |
| `passphrase` | string | ❌ | API Passphrase（币安不需要） | `""` |
| `proxies` | object | ❌ | 代理配置（可选） | `{}` |
| `exchange` | int | ✅ | 交易所ID：`2`=币安 | `2` |

### 系统标识字段

| 字段 | 类型 | 必填 | 说明 | 示例 |
|-----|------|------|------|------|
| `uniqueName` | string | ⚠️ | 系统标识（可选，默认 `"ai_trading_system"`） | `"ai_trading_system"` |

---

## 操作示例

### 示例1：市价开多（带止盈止损）

**场景**：以市价开多仓，止盈60%，止损50%

```json
{
  "order_type": "open",
  "symbol": "POLUSDT",
  "positionSide": "LONG",
  "side": "BUY",
  "leverage": 20.0,
  "sums": "10000",
  "openAvgPx": 0.16739,
  "task_id": 23,
  "user_id": 2,
  "api_id": 0,
  "trade_trigger_mode": 1,
  "tp_trigger_px": 60.0,
  "sl_trigger_px": 50.0,
  "acc": {
    "key": "your_api_key",
    "secret": "your_api_secret",
    "passphrase": "",
    "proxies": {},
    "exchange": 2
  },
  "flag": "1",
  "uniqueName": "ai_trading_system"
}
```

### 示例2：市价平多

**场景**：平掉所有多仓

```json
{
  "order_type": "close",
  "symbol": "POLUSDT",
  "positionSide": "LONG",
  "side": "SELL",
  "leverage": 20.0,
  "sums": "10000",
  "openAvgPx": 0.16739,
  "task_id": 23,
  "user_id": 2,
  "api_id": 0,
  "trade_trigger_mode": 0,
  "tp_trigger_px": 0.0,
  "sl_trigger_px": 0.0,
  "acc": {
    "key": "your_api_key",
    "secret": "your_api_secret",
    "passphrase": "",
    "proxies": {},
    "exchange": 2
  },
  "flag": "1",
  "uniqueName": "ai_trading_system"
}
```

### 示例3：市价开空（带止盈止损）

**场景**：以市价开空仓，止盈60%，止损50%

```json
{
  "order_type": "open",
  "symbol": "POLUSDT",
  "positionSide": "SHORT",
  "side": "SELL",
  "leverage": 20.0,
  "sums": "10000",
  "openAvgPx": 0.16739,
  "task_id": 23,
  "user_id": 2,
  "api_id": 0,
  "trade_trigger_mode": 1,
  "tp_trigger_px": 60.0,
  "sl_trigger_px": 50.0,
  "acc": {
    "key": "your_api_key",
    "secret": "your_api_secret",
    "passphrase": "",
    "proxies": {},
    "exchange": 2
  },
  "flag": "1",
  "uniqueName": "ai_trading_system"
}
```

### 示例4：市价平空

**场景**：平掉所有空仓

```json
{
  "order_type": "close",
  "symbol": "POLUSDT",
  "positionSide": "SHORT",
  "side": "BUY",
  "leverage": 20.0,
  "sums": "10000",
  "openAvgPx": 0.16739,
  "task_id": 23,
  "user_id": 2,
  "api_id": 0,
  "trade_trigger_mode": 0,
  "tp_trigger_px": 0.0,
  "sl_trigger_px": 0.0,
  "acc": {
    "key": "your_api_key",
    "secret": "your_api_secret",
    "passphrase": "",
    "proxies": {},
    "exchange": 2
  },
  "flag": "1",
  "uniqueName": "ai_trading_system"
}
```

### 示例5：限价开多（带止盈止损）

**场景**：以限价0.17655开多仓，止盈价0.28248，止损价0.083695

```json
{
  "order_type": "open",
  "symbol": "POLUSDT",
  "positionSide": "LONG",
  "side": "BUY",
  "leverage": 20.0,
  "sums": "10000",
  "openAvgPx": 0.17655,
  "limit_price": 0.17655,
  "order_type_binance": "LIMIT",
  "timeInForce": "GTC",
  "task_id": 23,
  "user_id": 2,
  "api_id": 0,
  "trade_trigger_mode": 1,
  "tp_trigger_px": 0.28248,
  "sl_trigger_px": 0.083695,
  "acc": {
    "key": "your_api_key",
    "secret": "your_api_secret",
    "passphrase": "",
    "proxies": {},
    "exchange": 2
  },
  "flag": "1",
  "uniqueName": "ai_trading_system"
}
```

### 示例6：限价平多

**场景**：以限价平掉所有多仓

```json
{
  "order_type": "close",
  "symbol": "POLUSDT",
  "positionSide": "LONG",
  "side": "SELL",
  "leverage": 20.0,
  "sums": "10000",
  "openAvgPx": 0.17655,
  "limit_price": 0.17655,
  "order_type_binance": "LIMIT",
  "timeInForce": "GTC",
  "task_id": 23,
  "user_id": 2,
  "api_id": 0,
  "trade_trigger_mode": 0,
  "tp_trigger_px": 0.0,
  "sl_trigger_px": 0.0,
  "acc": {
    "key": "your_api_key",
    "secret": "your_api_secret",
    "passphrase": "",
    "proxies": {},
    "exchange": 2
  },
  "flag": "1",
  "uniqueName": "ai_trading_system"
}
```

### 示例7：限价开空（带止盈止损）

**场景**：以限价0.17655开空仓，止盈价0.07062，止损价0.26483

```json
{
  "order_type": "open",
  "symbol": "POLUSDT",
  "positionSide": "SHORT",
  "side": "SELL",
  "leverage": 20.0,
  "sums": "10000",
  "openAvgPx": 0.17655,
  "limit_price": 0.17655,
  "order_type_binance": "LIMIT",
  "timeInForce": "GTC",
  "task_id": 23,
  "user_id": 2,
  "api_id": 0,
  "trade_trigger_mode": 1,
  "tp_trigger_px": 0.07062,
  "sl_trigger_px": 0.26483,
  "acc": {
    "key": "your_api_key",
    "secret": "your_api_secret",
    "passphrase": "",
    "proxies": {},
    "exchange": 2
  },
  "flag": "1",
  "uniqueName": "ai_trading_system"
}
```

### 示例8：限价平空

**场景**：以限价平掉所有空仓

```json
{
  "order_type": "close",
  "symbol": "POLUSDT",
  "positionSide": "SHORT",
  "side": "BUY",
  "leverage": 20.0,
  "sums": "10000",
  "openAvgPx": 0.17655,
  "limit_price": 0.17655,
  "order_type_binance": "LIMIT",
  "timeInForce": "GTC",
  "task_id": 23,
  "user_id": 2,
  "api_id": 0,
  "trade_trigger_mode": 0,
  "tp_trigger_px": 0.0,
  "sl_trigger_px": 0.0,
  "acc": {
    "key": "your_api_key",
    "secret": "your_api_secret",
    "passphrase": "",
    "proxies": {},
    "exchange": 2
  },
  "flag": "1",
  "uniqueName": "ai_trading_system"
}
```

---

## 操作说明

### 市价单 vs 限价单

| 特性 | 市价单 | 限价单 |
|-----|--------|--------|
| 成交方式 | 立即按市价成交 | 达到限价才成交 |
| 识别字段 | 无 `order_type_binance` 或为 `MARKET` | `order_type_binance` = `"LIMIT"` |
| 限价字段 | 不需要 | 必须提供 `limit_price` |
| 有效期 | 不适用 | `timeInForce` = `"GTC"` |
| 止盈止损模式 | **百分比模式**（如 `60.0` 表示60%） | **价格模式**（如 `0.28248`） |
| 止盈止损设置时机 | 开仓后立即设置 | 限价单提交后立即设置（不等待成交） |

### 方向组合规则

| 操作 | positionSide | side | 说明 |
|-----|-------------|------|------|
| 开多 | `LONG` | `BUY` | 买入开多 |
| 平多 | `LONG` | `SELL` | 卖出平多 |
| 开空 | `SHORT` | `SELL` | 卖出开空 |
| 平空 | `SHORT` | `BUY` | 买入平空 |

### 止盈止损计算

#### 市价单（百分比模式）

假设当前市价为 `0.16739`，开多仓：

- **止盈60%**：`tp_trigger_px = 60.0`
  - 止盈价格 = `0.16739 × (1 + 60/100) = 0.267824`
  
- **止损50%**：`sl_trigger_px = 50.0`
  - 止损价格 = `0.16739 × (1 - 50/100) = 0.083695`

#### 限价单（价格模式）

假设限价价格为 `0.17655`，开多仓：

- **止盈价格**：`tp_trigger_px = 0.28248`（直接指定）
- **止损价格**：`sl_trigger_px = 0.083695`（直接指定）

---

## 注意事项

### 1. 交易数量计算

有两种方式指定交易数量：

#### 方式1：直接指定数量（传统方式）

```python
sums = "10000"  # 直接指定交易数量（张数）
```

#### 方式2：根据保证金计算（推荐）

根据保证金、杠杆和价格自动计算交易数量：

**计算公式**：
```
sums = 保证金 * 杠杆 / 价格
```

**示例**：
- 保证金 = 100 USDT
- 杠杆 = 20x
- 价格 = 0.16739（市价单）或 0.17655（限价单）
- 计算：sums = 100 * 20 / 0.16739 ≈ 11944 张

**注意事项**：
- **市价单**：使用当前市价计算数量
- **限价单**：使用限价（limit_price）计算数量
- 计算后的数量会自动格式化，符合币安精度要求
- 名义价值（数量 × 价格）必须 ≥ 5 USDT，系统会自动调整

### 2. 数量精度

- `sums` 字段必须是**字符串格式**
- 数量必须符合币安交易对的 `stepSize` 精度要求
- 名义价值（数量 × 价格）必须 ≥ 5 USDT

**常见交易对精度**：
- `POLUSDT`: `stepSize = 1.0`（整数）
- `BTCUSDT`: `stepSize = 0.001`（3位小数）
- `ETHUSDT`: `stepSize = 0.001`（3位小数）

### 3. 价格精度

- 限价单的 `limit_price` 必须符合币安交易对的 `tickSize` 精度要求
- 止盈止损价格也必须符合 `tickSize` 精度

**常见价格精度**：
- `POLUSDT`: `tickSize = 0.00001`（5位小数）
- `BTCUSDT`: `tickSize = 0.01`（2位小数）
- `ETHUSDT`: `tickSize = 0.01`（2位小数）

### 4. 止盈止损设置

#### 市价单
- 使用**百分比**，相对开仓价格计算
- 开多：止盈在价格上方，止损在价格下方
- 开空：止盈在价格下方，止损在价格上方

#### 限价单
- 使用**具体价格**，必须直接指定
- 限价单提交后**立即**设置条件委托单（不等待成交）
- 限价单成交后，条件委托单自动激活

### 5. 孤儿订单清理

系统每15秒自动清理孤儿订单：
- 没有持仓且没有基础限价单的条件委托单会被清理
- 有基础限价单的条件委托单会被保留

### 6. API 账户配置

- `acc.key` 和 `acc.secret` 必须正确配置
- `flag` 字段：`"0"`=实盘，`"1"`=模拟盘
- 确保API有相应的交易权限

### 7. 推送方式

```python
import json
import redis

# 连接 Redis
r = redis.Redis(
    host='38.147.173.111',
    port=6379,
    password='112233Ww..',
    db=8,
    decode_responses=False
)

# 准备交易 JSON
trade_json = {
    # ... 交易数据 ...
}

# 推送消息
json_str = json.dumps(trade_json, ensure_ascii=False)
r.lpush('TASK_ADD_TRADE', json_str)
```

### 8. 错误处理

- 检查 Redis 连接状态
- 验证 JSON 格式正确性
- 确保必填字段完整
- 检查数量和价格的精度要求

---

## 快速参考

### Python 示例代码

```python
import json
import redis

def push_trade_order(order_type, symbol, position_side, side, 
                     leverage, sums, price, task_id, user_id, api_id,
                     trade_trigger_mode=0, tp_trigger_px=0.0, sl_trigger_px=0.0,
                     is_limit_order=False, limit_price=None,
                     api_key="", api_secret="", flag="1"):
    """
    推送交易订单到 Redis（精简版，只包含实际使用的字段）
    
    Args:
        order_type: "open", "close", "reduce"
        symbol: 交易对，如 "POLUSDT"
        position_side: "LONG" 或 "SHORT"
        side: "BUY" 或 "SELL"
        leverage: 杠杆倍数
        sums: 数量（字符串）
        price: 价格
        task_id: 任务ID
        user_id: 用户ID
        api_id: API ID
        trade_trigger_mode: 0=关闭, 1=开启
        tp_trigger_px: 止盈（市价单：百分比；限价单：价格）
        sl_trigger_px: 止损（市价单：百分比；限价单：价格）
        is_limit_order: 是否限价单
        limit_price: 限价（仅限价单需要）
        api_key: API Key
        api_secret: API Secret
        flag: "0"=实盘, "1"=模拟盘
    """
    trade_json = {
        # 核心交易字段
        "order_type": order_type,
        "symbol": symbol,
        "positionSide": position_side,
        "side": side,
        "leverage": float(leverage),
        "sums": str(sums),
        "openAvgPx": float(price),
        
        # 账户标识字段
        "task_id": int(task_id),
        "user_id": int(user_id),
        "api_id": int(api_id),
        
        # 止盈止损字段
        "trade_trigger_mode": int(trade_trigger_mode),
        "tp_trigger_px": float(tp_trigger_px),
        "sl_trigger_px": float(sl_trigger_px),
        
        # 账户信息
        "acc": {
            "key": api_key,
            "secret": api_secret,
            "passphrase": "",
            "proxies": {},
            "exchange": 2
        },
        
        # 系统标识
        "flag": flag,
        "uniqueName": "ai_trading_system"
    }
    
    # 限价单额外字段
    if is_limit_order:
        trade_json["order_type_binance"] = "LIMIT"
        trade_json["limit_price"] = float(limit_price)
        trade_json["timeInForce"] = "GTC"
    
    # 连接 Redis 并推送
    r = redis.Redis(
        host='38.147.173.111',
        port=6379,
        password='112233Ww..',
        db=8,
        decode_responses=False
    )
    
    json_str = json.dumps(trade_json, ensure_ascii=False)
    r.lpush('TASK_ADD_TRADE', json_str)
    print(f"✅ 推送成功: {order_type} {position_side} {symbol}")

# 使用示例
# 市价开多
push_trade_order(
    order_type="open",
    symbol="POLUSDT",
    position_side="LONG",
    side="BUY",
    leverage=20.0,
    sums="10000",
    price=0.16739,
    task_id=23,
    user_id=2,
    api_id=0,
    trade_trigger_mode=1,
    tp_trigger_px=60.0,  # 百分比
    sl_trigger_px=50.0,  # 百分比
    api_key="your_key",
    api_secret="your_secret"
)

# 限价开多
push_trade_order(
    order_type="open",
    symbol="POLUSDT",
    position_side="LONG",
    side="BUY",
    leverage=20.0,
    sums="10000",
    price=0.17655,
    task_id=23,
    user_id=2,
    api_id=0,
    trade_trigger_mode=1,
    tp_trigger_px=0.28248,  # 具体价格
    sl_trigger_px=0.083695,  # 具体价格
    is_limit_order=True,
    limit_price=0.17655,
    api_key="your_key",
    api_secret="your_secret"
)
```

---

## 总结

本文档提供了完整的交易服务 API 使用说明，包括：
- ✅ 市价单和限价单的完整示例
- ✅ 所有字段的详细说明
- ✅ 8个常见操作场景的 JSON 示例
- ✅ Python 快速集成代码
- ✅ 注意事项和最佳实践

如有问题，请参考精简版测试脚本：
- 市价单：`test_push_trade_to_redis_minimal.py`
- 限价单：`test_push_limit_order_to_redis_minimal.py`

## 测试脚本使用说明

### 环境变量配置

#### 市价单测试脚本（`test_push_trade_to_redis_minimal.py`）

```bash
# 交易参数
export TEST_SYMBOL="POLUSDT"           # 交易对
export TEST_PRICE="0.16739"            # 当前市价（用于计算）
export TEST_LEVERAGE="20.0"            # 杠杆倍数

# 交易数量配置（二选一）
export TEST_MARGIN="100.0"             # 保证金（USDT，推荐）- 会根据保证金、杠杆和市价计算数量
# 或者
export TEST_AMOUNT="10000"             # 直接指定数量（字符串）

# 止盈止损配置（百分比模式）
export TEST_TRADE_TRIGGER_MODE="1"     # 0=关闭, 1=开启
export TEST_TP_TRIGGER_PX="60.0"       # 止盈比例（百分比）
export TEST_SL_TRIGGER_PX="50.0"       # 止损比例（百分比）
```

#### 限价单测试脚本（`test_push_limit_order_to_redis_minimal.py`）

```bash
# 交易参数
export TEST_SYMBOL="POLUSDT"           # 交易对
export TEST_PRICE="0.17560"            # 当前市价（用于计算限价）
export TEST_LEVERAGE="20.0"            # 杠杆倍数

# 交易数量配置（二选一）
export TEST_MARGIN="100.0"             # 保证金（USDT，推荐）- 会根据保证金、杠杆和限价计算数量
# 或者
export TEST_AMOUNT="10000"             # 直接指定数量（字符串）

# 限价单配置
export TEST_LIMIT_PRICE_OFFSET="0"     # 限价单价格偏移（百分比），0表示使用市价

# 止盈止损配置（价格模式）
export TEST_TRADE_TRIGGER_MODE="1"     # 0=关闭, 1=开启
export TEST_TP_PERCENT="1.0"           # 止盈百分比（用于计算止盈价格）
export TEST_SL_PERCENT="1.0"           # 止损百分比（用于计算止损价格）
```

### 使用示例

#### 示例1：使用保证金计算数量（推荐）

```bash
# 设置保证金和杠杆，系统自动计算数量
export TEST_MARGIN="100.0"    # 100 USDT 保证金
export TEST_LEVERAGE="20.0"   # 20倍杠杆
export TEST_PRICE="0.16739"   # 当前市价

# 运行测试脚本
python test_push_trade_to_redis_minimal.py 1  # 市价开多

# 系统会自动计算：
# 数量 = 100 * 20 / 0.16739 ≈ 11944 张
```

#### 示例2：直接指定数量（传统方式）

```bash
# 直接指定数量
export TEST_AMOUNT="10000"    # 10000 张

# 运行测试脚本
python test_push_trade_to_redis_minimal.py 1  # 市价开多

# 系统会使用指定的数量
```

### 数量计算说明

- **市价单**：使用 `TEST_PRICE`（当前市价）计算数量
  - 公式：`sums = TEST_MARGIN * TEST_LEVERAGE / TEST_PRICE`
  
- **限价单**：使用 `limit_price`（限价）计算数量
  - 公式：`sums = TEST_MARGIN * TEST_LEVERAGE / limit_price`
  - `limit_price = TEST_PRICE * (1 + TEST_LIMIT_PRICE_OFFSET / 100)`

### 优先级说明

如果同时设置了 `TEST_MARGIN` 和 `TEST_AMOUNT`：
- 优先使用 `TEST_AMOUNT`（直接指定的数量）
- 如果 `TEST_AMOUNT` 为 `None` 或未设置，则使用 `TEST_MARGIN` 计算数量

