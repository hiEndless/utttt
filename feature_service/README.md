# feature_service

`feature_service` 是目标架构中的 **Feature Layer**，位于 `data_server` 之后、`event_center_new` 和 `market_state_engine` 之前。

目标收敛架构：

```text
data_server
  -> feature_service
    -> event_center_new
    -> market_state_engine
      -> agent_server_new
        -> execution_service
```

## 定位

`feature_service` 的职责不是采集原始数据，也不是产出交易决策，而是把原始数据加工为可复用的结构化特征。

一句话定义：

> `feature_service` 负责把 market data 变成 feature data。

## 核心职责

`feature_service` 只负责以下能力：

- indicators
  - EMA / RSI / MACD / KDJ / MFI / MA / BollingerBand / Williams
- derived metrics
  - volatility burst
  - funding extreme
  - open interest delta
  - orderbook imbalance
  - liquidation density
- structure snapshots
  - multi-timeframe structure
  - trend memory
  - participant positioning
  - liquidity structure
  - support / resistance candidates
- feature normalization
  - 统一字段语义
  - 统一时间戳与版本
  - 统一 symbol / exchange / timeframe 表达
- feature serving
  - 对 `event_center_new` 输出“事件化特征输入”
  - 对 `market_state_engine` 输出“原始结构快照 / 特征集合”

## 不负责的事情

`feature_service` 不负责：

- 原始数据采集
  - 这是 `data_server`
- 事件去重、分类、优先级
  - 这是 `event_center_new`
- regime detection / anomaly synthesis / MSL generation
  - 这是 `market_state_engine`
- signal evaluation / strategy planning / risk gating
  - 这是 `agent_server_new`
- order routing / exchange execution / reconciliation
  - 这是 `execution_service`

## 输入与输出

### 输入

来自 `data_server` 的原始输入：

- kline
- ticker / mark price
- orderbook / depth
- open interest
- funding
- long-short ratios
- liquidation feed
- news / social / onchain raw feeds（未来）

### 输出

对下游输出两类内容：

1. `FeatureSnapshot`
   - 给 `market_state_engine`
   - 用于状态推断
2. `FeatureEventCandidate`
   - 给 `event_center_new`
   - 用于事件化处理

### 推荐的稳定输出

- `GET /internal/feature-service/features/{exchange}/{symbol}`
  - 返回完整 feature snapshot
- `GET /internal/feature-service/raw-structure/{exchange}/{symbol}`
  - 返回标准化 raw market structure

## 与相邻服务的边界

### 对 `data_server`

`feature_service` 只消费原始市场数据，不反向要求 `data_server` 理解 feature 语义。

### 对 `event_center_new`

`feature_service` 提供“可事件化的 feature 输入”，但不直接产出最终事件。

例如：

- `indicator_cross`
- `volatility_expansion`
- `funding_extreme`
- `oi_spike`

这些只是候选输入，不是事件中心的最终输出。

### 对 `market_state_engine`

`feature_service` 提供：

- `raw_market_structure`
- `feature_snapshot`
- `timeframe_features`

`market_state_engine` 再基于这些内容做：

- anomaly synthesis
- regime detection
- summary
- MSL generation

## 建议承接的现有能力

未来从现有代码迁移的重点来源：

- `data_server/binance/rest_binance/app/signals/*`
- `agent_server/agent_context/market_structure/*`
- 当前旧链路中用于拼 `market_structure` 的聚合逻辑

建议迁移策略：

1. 先迁指标计算
2. 再迁结构聚合
3. 最后替换旧的过渡实现

## 服务目录建议

```text
feature_service/
  README.md
  app.py
  main.py
  routes.py
  service.py
  contracts.py
  docs/
    api.md
    boundaries.md
    migration.md
  ports/
    raw_market_provider.py
    feature_store.py
  adapters/
    raw_market_http.py
    memory_feature_store.py
```

## 当前阶段目标

当前目录中的实现目标不是一次性做完全部 feature 计算，而是先固定：

- 服务边界
- HTTP 接口
- feature contract
- 与 `market_state_engine` 的对接方式

当前过渡实现已经改为：

- `feature_service` 自己负责组装 `raw_market_structure`
- 但底层 `orderbook / open_interest / horizons / behavioral` 仍通过兼容 adapter 复用旧实现
- 不再直接调用旧的最终 market structure 聚合器

## 下一步建议

优先实现顺序：

1. 固定 `raw_market_structure` schema
2. 实现 `GET /internal/feature-service/raw-structure/{exchange}/{symbol}`
3. 实现 `GET /internal/feature-service/features/{exchange}/{symbol}`
4. 把 `market_state_engine` 的 HTTP raw structure adapter 接到这个服务
5. 再逐步迁移真实计算逻辑

## 当前对接约定

`market_state_engine` 当前会优先通过以下接口读取 raw structure：

- `GET /internal/feature-service/raw-structure/{exchange}/{symbol}`

因此这个接口应视为优先稳定的内部契约。
