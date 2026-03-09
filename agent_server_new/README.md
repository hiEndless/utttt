# agent_server_new

项目级新架构总览：`/ARCHITECTURE_NEW.md`

`agent_server_new` 是目标架构中的 **Decision Agent**，只负责决策层，不再承载长期稳定的状态生产职责，也不负责真实执行。

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

`agent_server_new` 只承担以下职责：

- consume `signal_event`
- consume `active_events`
- consume `MSL`
- consume `position_context`
- 做 signal evaluation
- 做 intent resolve / rule planning
- 做 strategy gating / risk gating
- 产出 `ExecutionPlan`
- 产出 `DecisionTrace`

`agent_server_new` 不承担以下职责：

- 不采集原始市场数据
- 不计算指标和结构特征
- 不维护事件中心
- 不长期拥有 `MarketStateEngine`
- 不直接下单执行
- 不承担订单路由、成交回执对账、仓位对账

一句话定义：

> `agent_server_new` 只做“基于既有市场状态与事件上下文的决策”，不做“状态生成”，也不做“执行落地”。

## 目标输入输出

### 输入

来自两个上游：

1. `event_center_new`
   - `signal_event`
   - `active_events`
2. `market_state_engine`
   - `MSL`
   - `key_features`
   - `anomaly_flags`

再叠加一个内部或外部上下文：

- `position_context`

### 输出

输出给 `execution_service`：

- `ExecutionPlan`

输出给观测与复盘系统：

- `DecisionTrace`

## 推荐决策链路

```text
signal_event + active_events + MSL + position_context
  -> SignalEvaluator
  -> IntentResolver
  -> RulePlanner
  -> StrategyGate
  -> RiskGate
  -> ExecutionPlanner
  -> ExecutionPlan
  -> DecisionTrace
```

其中：

- LLM 只负责语义判断、解释、冲突权衡
- 硬约束必须在确定性 gate 中生效
- `ExecutionPlan` 是决策层终点，不是执行层入口代码

## 必须从 `agent_server_new` 中剥离的能力

如果严格对齐目标架构，以下能力不应继续长期放在 `agent_server_new` 内部：

- `market_state_engine`
- `MSL` 生产逻辑
- 基于 raw structure 的 anomaly synthesis
- 状态层 feature aggregation
- 长周期状态快照存储

这些都应收敛到未来独立的 `market_state_engine`。

## 推荐边界

### 应该保留在 `agent_server_new` 的能力

- decision workflow orchestration
- expert prompt building
- structured expert outputs
- intent resolution
- rule planning
- strategy gating
- risk gating
- execution planning
- decision trace / explainability

### 不应该保留在 `agent_server_new` 的能力

- raw market structure parsing
- feature aggregation
- event normalization
- event dedup / correlation
- exchange order execution
- reconciliation / fill tracking

## 目录建议

推荐收敛后的目录：

```text
agent_server_new/
  README.md
  app/
    workflows/
      trade_event_workflow.py
  domain/
    contracts.py             # SignalVerdict / Intent / RulePlan / ExecutionPlan / DecisionTrace contract refs
    intent_resolver.py
    rule_planner.py
    strategy_gate.py
    risk_gate.py
    execution_planner.py
  experts/
    base/
    signal_evaluator.py
  ports/
    event_input.py
    market_state.py
    position.py
    execution_plan_sink.py
    trace_sink.py
  adapters/
    event_center_adapter.py
    market_state_adapter.py
    position_context_adapter.py
  observability/
    decision_trace.py
```

说明：

- `domain/market_state_engine.py` 不应长期保留在这里
- `compat/market_structure.py` 只允许作为过渡兼容层
- `ports` 只描述输入输出，不描述 Redis/HTTP 细节

## 需要搬走的文件与能力

以下文件建议迁到未来的 `market_state_engine` 服务：

- `domain/market_state_engine.py`
- `domain/msl.py`

以下能力建议改造成状态层输入适配器，随后迁移到独立状态层服务：

- raw structure provider
- market state provider adapter

原因：

- 它们的核心职责是从 `market_structure/raw features` 生成状态摘要
- 这属于状态层，不属于决策层

以下文件应继续保留在 `agent_server_new`：

- `domain/intent_resolver.py`
- `domain/rule_planner.py`
- `domain/strategy_gate.py`
- `domain/risk_gate.py`
- `domain/execution_planner.py`
- `experts/signal_evaluator.py`
- `observability/decision_trace.py`
- `app/workflows/trade_event_workflow.py`

## 建议改名的 contract

为了让层次更清晰，建议把 contract 按服务边界区分。

### 属于 `market_state_engine`

- `MarketStateMSL`
- `MarketStateFeatures`
- `AnomalyFlags`
- `KeyMarketFeatures`

### 属于 `agent_server_new`

- `SignalVerdict`
- `IntentDecision`
- `RulePlan`
- `ExecutionPlan`
- `DecisionTrace`

如果当前 `domain/contracts.py` 同时放了状态层与决策层对象，建议拆分。

建议拆成：

- `market_state_engine/contracts.py`
- `agent_server_new/domain/contracts.py`

## 必须切断的依赖

`agent_server_new` 必须遵守以下依赖规则：

- 可以依赖：
  - `event_center_new` 发布的事件协议
  - `market_state_engine` 发布的状态协议
  - `position_context` port
- 不可以依赖：
  - `data_server` 的原始结构输出
  - `feature_service` 的内部存储结构
  - `execution_service` 的交易所 SDK 细节

严格规则：

> `agent_server_new` 不允许直接消费 raw structure 来生成最终 MSL。

否则状态层与决策层边界会再次塌陷。

## 需要调整的工作流

当前 `app/workflows/trade_event_workflow.py` 的总体方向是对的，但还需要继续收窄：

当前工作流里仍然通过 `ContextBuilder` 间接吸收市场状态构建逻辑，这只是过渡方案。

最终应改为：

1. 从 `event_center_new` 读入：
   - `signal_event`
   - `active_events`
2. 从 `market_state_engine` 读入：
   - `MSL`
   - `key_features`
   - `anomaly_flags`
3. 从 position provider 读入：
   - `position_context`
4. 决策层只做决策，不做状态拼装

也就是说：

- `ContextBuilder` 最终只应做轻量 assemble
- 不应继续承担 market state build

## 与 `execution_service` 的接口约定

`agent_server_new` 对执行层只输出标准计划，不输出执行细节。

建议固定为：

- `ExecutionPlan`
  - action
  - direction
  - sizing
  - allowance
  - confidence
  - notes
  - trace_ref

执行层负责：

- plan validation
- order routing
- exchange execution
- fill / reject handling
- reconciliation

决策层不应知道：

- 具体交易所 API 重试策略
- 下单幂等 token
- 成交回报状态机
- 仓位对账细节

## 迁移清单

### 第一阶段：逻辑剥离

1. 明确 `market_state_engine.py` 只是临时托管在本服务
2. 禁止新增任何 raw structure -> MSL 的新逻辑到决策层 workflow
3. 把 `domain/contracts.py` 中状态层对象和决策层对象分开

### 第二阶段：依赖反转

1. 新增 `ports/market_state.py`
2. 工作流通过 port 获取：
   - `MSL`
   - `key_features`
   - `anomaly_flags`
3. 删除 workflow 对兼容市场结构模块的直接依赖

### 第三阶段：物理拆分

1. 把 `domain/market_state_engine.py` 搬到新服务
2. 把 `domain/msl.py` 搬到新服务
3. 把 raw structure / market state adapter 下沉到独立状态层服务
4. `agent_server_new` 只保留 `market_state` port 和 adapter client

## 当前版本相对目标架构的问题

当前版本最大的偏差有三个：

1. `MarketStateEngine` 仍在 `agent_server_new` 内
2. 部分状态层 contract 仍和决策层 contract 混在一起
3. workflow 还承担了部分状态组装责任

这些都不是方向错误，但说明当前仍处于“状态层和决策层半分离”的阶段。

## 收敛后的定义

`agent_server_new` 最终应该成为：

> 一个纯决策服务，消费事件层和状态层的标准输入，输出稳定的 `ExecutionPlan` 与 `DecisionTrace`，而不是继续兼任市场状态生产器或执行引擎。
