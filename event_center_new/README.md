# event_center_new

`event_center_new` 是目标架构中的 **Event Center**，只负责事件层，不负责市场状态归纳，不负责交易决策，不负责执行。

目标收敛架构：

```text
data_server
  -> feature_service
    -> event_center_new
      -> market_state_engine
        -> agent_server_new
          -> execution_service
```

## 在总架构中的职责

`event_center_new` 只承担以下职责：

- ingest：接入多源事件输入（exchange / onchain / news / social / liquidation / strategy signal）
- normalize：把不同来源统一成稳定的事件契约
- dedup：做去重、幂等、trace 传递
- correlate：把同一时间窗、同一资产、同一主题的事件建立关联
- classify：做事件类型、事件层级、时间跨度、触发性质分类
- prioritize：做事件重要性和路由优先级排序

`event_center_new` 不承担以下职责：

- 不生成 MSL
- 不输出市场 regime / structure summary
- 不做 strategy planning / risk gating
- 不输出 `ExecutionPlan`
- 不直接依赖 `agent_server_new` 的领域契约

一句话定义：

> Event Center 的输出应该是“经过清洗、归一、关联、排序后的事件与证据”，而不是“市场结论”或“交易结论”。

## 输入与输出

### 输入

来自上游两类来源：

- `data_server`：原始事件流
  - exchanges
  - onchain
  - news
  - social
- `feature_service`：特征派生结果中产生的事件型输出
  - indicator crosses
  - volatility burst
  - open interest jump
  - liquidation cluster
  - structure break / reclaim

### 输出

输出给两个下游：

1. `market_state_engine`
   - 消费 selected events / evidence / correlation groups / priority hints
2. `agent_server_new`
   - 消费 signal_event / active_events

建议输出拆成两类：

- `SelectedEvent`
  - 适合进入状态层或决策层的标准事件
- `EventBatch`
  - 某个资产某个时间窗内的活跃事件集合，包含去重和优先级结果

## 推荐边界

### 应该保留在 `event_center_new` 的能力

- source adapters
- event normalization
- evidence extraction
- ttl / decay
- dedup / idempotency
- correlation / clustering
- classification / tagging
- prioritization / routing hints
- event memory（短期事件记忆）

### 不应该留在 `event_center_new` 的能力

- `MarketContext`
- `MSL`
- market regime inference
- anomaly synthesis（跨 feature 的市场异常归纳）
- key level summary
- trade intent / execution planning

如果某个处理步骤开始回答“现在市场是什么状态”，它就已经不属于 `event_center_new`。

## 推荐契约

建议把当前契约收敛为纯事件中心语义。

### 保留

- `EventEnvelope`
- `Evidence`
- `EventTrace`

### 新增或重命名

- `L0Output` -> `ClassifiedEvent`
- `L1Output` -> `PrioritizedEvent`
- `FinalOutput` -> `SelectedEvent`

原因：

- `L0/L1/Final` 是旧流水线命名，表达的是处理阶段，不表达业务语义
- `Classified / Prioritized / Selected` 更贴近 Event Center 的真实职责
- `Final` 这个词容易诱导事件中心越界去做“最终结论”

### 应删除或迁出

- `MarketContext`

原因：

- `MarketContext` 属于状态层或决策层组合对象
- 事件中心不应持有 `msl`
- 事件中心不应 import `agent_server_new.domain.contracts`

## 目录建议

推荐收敛后的目录：

```text
event_center_new/
  README.md
  docs/
    schema.md
    migration.md
  ec/
    contracts.py              # EventEnvelope / Evidence / ClassifiedEvent / PrioritizedEvent / SelectedEvent
    pipeline/
      normalize.py
      dedup.py
      correlate.py
      classify.py
      prioritize.py
      route.py
    sources/
      base.py
      exchange/
      onchain/
      news/
      social/
    storage/
      event_memory.py
    routing/
      selectors.py
```

说明：

- 不再在 `event_center_new` 中维护 `MarketContext`
- 不再以 `L0/L1/Final` 作为长期稳定语言
- `route.py` 只做路由选择，不做市场状态推理

## 需要搬走的文件与能力

以下能力不应继续留在 `event_center_new`：

- `ec/contracts.py` 中的 `MarketContext`
  - 处理方式：删除，或迁到未来的 `market_state_engine/contracts.py`
- 任何依赖 `MarketStateMSL` 的类型声明
  - 处理方式：改为事件中心本地契约，不引用下游类型

如果未来在 `event_center_new` 中新增了这些内容，也应直接放到新服务而不是继续堆在这里：

- anomaly synthesis
- regime detection
- structure summary
- MSL generation

这些都应进入 `market_state_engine`。

## 必须切断的依赖

`event_center_new` 必须遵守以下依赖方向：

- 可以依赖：
  - `data_server` 的输出协议
  - `feature_service` 的输出协议
  - 自己的 `contracts / pipeline / storage`
- 不可以依赖：
  - `agent_server_new.domain.*`
  - `market_state_engine.domain.*`
  - `execution_service.*`

严格规则：

> `event_center_new` 只能向下游发布事件契约，不能 import 下游服务的领域对象。

## 迁移清单

### 第一阶段：切边界

1. 从 `ec/contracts.py` 删除 `MarketContext`
2. 删除 `AgentMarketStateMSL` 的 import fallback
3. 把 `L0Output / L1Output / FinalOutput` 改名为事件语义名
4. 把所有与 `msl` 相关字段从事件中心契约中移除

### 第二阶段：稳定输出

1. 固定 `EventEnvelope` / `Evidence` / `SelectedEvent` schema
2. 在 `docs/schema.md` 中明确：
   - ingest schema
   - normalized schema
   - prioritized schema
   - selected schema
3. 对外只暴露这些 schema，不暴露内部阶段对象

### 第三阶段：为状态层提供干净输入

`event_center_new` 对 `market_state_engine` 输出建议固定为：

- `selected_event`
- `event_window`
- `correlated_evidences`
- `priority`
- `trace`

而不是：

- `market_state`
- `regime`
- `summary`
- `msl`

## 与其他服务的接口约定

### 对 `feature_service`

输入来自 `feature_service` 的应该是“事件化特征”，例如：

- `indicator_cross`
- `volatility_expansion`
- `funding_extreme`
- `open_interest_spike`
- `liquidity_gap_detected`

事件中心不负责重新计算 feature。

### 对 `market_state_engine`

事件中心给状态层的是：

- 多源事件
- 证据集合
- 关联关系
- 时间衰减后的活跃事件集合

状态层自己决定如何结合 feature 做 regime / anomaly / MSL。

### 对 `agent_server_new`

事件中心可以直接给决策层提供：

- `signal_event`
- `active_events`

但这些都必须是事件语义，而不是市场状态语义。

## 当前版本的主要问题

当前版本相对目标架构，主要有两个问题：

1. `ec/contracts.py` 里仍然存在 `MarketContext`
2. `event_center_new` 仍然感知 `MarketStateMSL`

这两点会导致职责污染，必须优先修正。

## 收敛后的定义

`event_center_new` 最终应该成为：

> 一个独立的事件中台，负责把多源原始输入整理成可消费、可追踪、可排序的事件流，为 `market_state_engine` 和 `agent_server_new` 提供干净事件输入。

