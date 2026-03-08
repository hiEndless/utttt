# market_state_engine

`market_state_engine` 是目标架构中的 **State Layer**，位于 `feature_service` 之后、`agent_server_new` 之前。

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

`market_state_engine` 的职责不是采集数据，也不是做交易决策，而是把结构化特征和已筛选事件归纳成稳定市场状态。

一句话定义：

> `market_state_engine` 负责把 feature data 变成 state data。

## 核心职责

`market_state_engine` 只负责以下能力：

- consume feature snapshots
- consume raw market structure
- anomaly synthesis
- regime detection
- structure summary
- MSL generation
- key_features extraction
- state serving

## 不负责的事情

`market_state_engine` 不负责：

- 原始市场数据采集
  - 这是 `data_server`
- feature 计算与标准化
  - 这是 `feature_service`
- 事件去重、分类、优先级
  - 这是 `event_center_new`
- signal evaluation / rule planning / risk gating
  - 这是 `agent_server_new`
- 下单执行与对账
  - 这是 `execution_service`

## 输入与输出

### 输入

当前主输入：

- `feature_service` 提供的 `raw_market_structure`

未来可扩展输入：

- `feature_snapshot`
- `selected_event`
- `active_events`

### 输出

输出给 `agent_server_new`：

- `MSL`
- `state_features`
- `anomaly_flags`

## 服务接口

当前最小接口：

- `GET /internal/market-state/healthz`
- `GET /internal/market-state/{exchange}/{symbol}`

返回体包含：

- `exchange`
- `symbol`
- `msl`
- `state_features`
- `anomaly_flags`
- `raw_market_structure`

## 目录说明

```text
market_state_engine/
  README.md
  app.py
  main.py
  routes.py
  service.py
  contracts.py
  engine.py
  msl.py
  docs/
    api.md
    boundaries.md
    migration.md
  ports/
    raw_structure_provider.py
    storage/
      feature_store.py
  adapters/
    raw_structure_http.py
    in_memory_feature_store.py
```

## 与相邻服务的边界

### 对 `feature_service`

`market_state_engine` 只通过 provider / HTTP adapter 读取标准化结构，不反向依赖 `feature_service` 内部实现。

当前正式对接路径：

- `GET /internal/feature-service/raw-structure/{exchange}/{symbol}`

### 对 `agent_server_new`

`market_state_engine` 只输出状态层 contract，不输出交易动作。

`agent_server_new` 应只消费：

- `MSL`
- `state_features`
- `anomaly_flags`

而不应直接读取 feature 层原始结构。

## 当前阶段

当前已经完成：

- 独立目录
- 独立 contract
- 独立服务骨架
- HTTP raw structure provider

当前仍是过渡阶段：

- 输入主要还是 `raw_market_structure`
- 尚未接入来自 `event_center_new` 的 selected events
- 尚未形成更完整的 state cache / replay 机制

## 下一步建议

优先实现顺序：

1. 固定 `raw_market_structure` schema
2. 让 `feature_service` 真实产出该结构
3. 再引入 `feature_snapshot`
4. 再接入 `selected_event / active_events`
5. 最后稳定 MSL schema 与版本演进策略
