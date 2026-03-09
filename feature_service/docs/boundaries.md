# feature_service Boundaries

## 只负责什么

- 指标计算
- 派生指标计算
- 结构化市场特征聚合
- 原始结构标准化
- feature 缓存与服务化输出

## 明确不负责什么

- 不采集交易所原始 feed
- 不做事件 dedup / classify / prioritize
- 不做 MSL / regime / anomaly synthesis
- 不做 signal evaluation / rule planning
- 不做 order execution

## 与下游的边界

### 给 `event_center_new`

提供：

- 可事件化的 feature candidate

不提供：

- 最终事件

### 给 `market_state_engine`

提供：

- `raw_market_structure`
- `feature_snapshot`

不提供：

- `MSL`
- `market summary`
- `regime`

## 反向依赖约束

`feature_service` 不应依赖：

- `event_center_new`
- `market_state_engine`
- `agent_server_new`
- `execution_service`

它只能向下游暴露 feature contract，而不能 import 下游领域对象。
