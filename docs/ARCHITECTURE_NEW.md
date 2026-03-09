# UTaker 新架构总览（2026-03-09）

本文档用于统一说明当前仓库的“新架构主链路”、模块边界、接口契约与迁移现状。

## 1. 架构主链路

```text
data_server
  -> feature_service
    -> event_center_new
    -> market_state_engine
      -> agent_server_new
        -> execution_service
```

说明：
- `feature_service` 同时服务 `event_center_new` 与 `market_state_engine`。
- `market_state_engine` 输出状态给 `agent_server_new`。
- `agent_server_new` 只做决策，不做执行。
- `execution_service` 是执行层，当前仓库已建立独立目录骨架（文档与 ports 层）。

## 1.1 正式事件流（冻结）

并行双通道：

1. 结构事件通道  
`event_center_new`（结构相关事件） -> `market_state_engine`（生成 MSL） -> `agent_server_new`

2. 外部事件通道  
`event_center_new`（舆情/链上/新闻等事件） -> `agent_server_new`（直接作为决策上下文）

约束：
- `market_state_engine` 只处理市场结构状态，不直接消费舆情/新闻/链上事件流。

## 1.2 业务流程（当前 vs 目标）

### 当前实现链路（可运行）

```text
feature_service(raw_structure/features)
  -> market_state_engine(msl/msl_meta/msl_bundle/cross_horizon)
    -> agent_server_new(workflow: SignalEvaluator -> IntentResolver -> RulePlanner -> HorizonPolicyGate -> StrategyGate -> RiskGate -> ExecutionPlanner)
```

说明：
- 当前 `event_center_new` 尚在重构中，但架构上已作为事件入口定义。
- 当前 `execution_service` 已有目录与文档骨架，尚未接管最终执行裁决。

### 目标收敛链路（冻结方向）

```text
event_center_new(signal_event + active_events)
  + market_state_engine(MSL + Key Evidence)
    -> agent_server_new(方向裁决与解释)
      -> execution_service(仓位/账户/PnL 风控 + 最终动作裁决)
```

说明：
- agent 输入收敛为：`MSL -> Key Evidence -> Active Events -> Signal Event`
- `Position Context` 下沉到 `execution_service`，不再作为 agent 裁决输入。
- execution 层成为“最终动作权威”。

## 2. 服务分层职责

### 2.1 data_server（数据层）
- 职责：采集和提供原始市场数据（K线、订单簿、OI、资金费率等）。
- 不负责：特征计算、状态推断、交易决策。

### 2.2 feature_service（特征层）
- 职责：把 market data 转成结构化 features。
- 核心输出：
  - `GET /internal/feature-service/raw-structure/{exchange}/{symbol}`
  - `GET /internal/feature-service/features/{exchange}/{symbol}`
- 架构要点：
  - 已按 `ports` 注入：`BehaviorProvider/HorizonsProvider/OpenInterestProvider/OrderbookProvider/IndicatorsProvider`
  - 可独立运行，不再运行时依赖旧 `agent_server`
  - 统一响应契约：`meta + data`
  - 关键结构数据不可用时返回 `503 feature_data_unavailable`

### 2.3 event_center_new（事件层）
- 职责：事件接入、标准化、去重、关联、分类、优先级排序。
- 产物：`SelectedEvent / EventBatch / Evidence`（事件语义对象）。
- 不负责：MSL 生成、市场状态归纳、交易决策。

### 2.4 market_state_engine（状态层）
- 职责：消费 features/raw structure，生成稳定状态输出（MSL、state_features、anomaly_flags）。
- 职责边界：只做市场结构状态分析（价格结构、订单簿、OI、波动、多周期一致性）。
- 不接入：新闻舆情、社媒、链上等外部事件源。
- 核心接口：
  - `GET /internal/market-state/healthz`
  - `GET /internal/market-state/{exchange}/{symbol}`
- 上游不可用策略：
  - 当 `feature_service` 返回 `503 feature_data_unavailable` 时，状态层返回 `status=data_unavailable`（HTTP 200，业务短路）。

### 2.5 agent_server_new（决策层）
- 职责：消费 `event_center_new + market_state_engine`，输出 `ExecutionPlan + DecisionTrace`。
- 不负责：原始数据采集、特征计算、状态生成、真实执行。

### 2.6 execution_service（执行层，目标态）
- 职责：执行计划校验、仓位与账户风控裁决（含 `position_context`）、路由下单、成交处理、对账与回执。
- 当前状态：目标架构角色已定义，代码形态仍在演进中。

## 3. 模块边界与依赖规则

强约束：
- 上游可以依赖下游“发布的契约”，不能依赖下游内部实现。
- `event_center_new` 不应 import `market_state_engine` 或 `agent_server_new` 的领域对象。
- `agent_server_new` 不应直接消费 raw structure 来生成 MSL。
- `feature_service` 不再直接 import 旧 `agent_server` 聚合逻辑。

推荐依赖方向：
- `data_server -> feature_service`
- `feature_service -> event_center_new / market_state_engine`
- `market_state_engine -> agent_server_new`
- `agent_server_new -> execution_service`

## 4. 项目现状（新旧并存）

### 4.1 新架构主模块
- `feature_service/`
- `event_center_new/`
- `market_state_engine/`
- `agent_server_new/`

### 4.2 旧模块（遗留链路，不作为本轮重构目标）
- `agent_server/`
- `event_center/`

说明：
- 旧模块可用于历史兼容或对照，不应作为新架构新增功能落地点。
- 你已明确：`agent_server` 不在本轮重构范围内。

## 5. 契约文档入口

- 联调速查：`CONTRACTS_QUICK_REF.md`
- 迁移执行清单：`REFACTOR_PLAYBOOK_NEW.md`
- 联调 cURL 示例：`CONTRACTS_CURL_EXAMPLES.md`
- 联调 HTTPie 示例：`CONTRACTS_HTTPIE_EXAMPLES.md`
- 一键冒烟脚本：`scripts/integration_smoke_new_arch.sh`
- 契约守卫脚本（CI 可用）：`scripts/check_feature_contract_guard.sh`
- Feature Schema 守卫脚本（CI 可用）：`scripts/check_feature_service_schema_guard.sh`
- State Engine 守卫脚本（CI 可用）：`scripts/check_market_state_engine_guard.sh`
- State->Agent 联动守卫脚本（CI 可用）：`scripts/check_state_to_agent_contract_guard.sh`
- 新架构守卫总入口（CI 可用）：`scripts/check_new_arch_guards.sh`
- Feature API：`feature_service/docs/api.md`
- Feature 边界：`feature_service/docs/boundaries.md`
- State API：`market_state_engine/docs/api.md`
- State 边界：`market_state_engine/docs/boundaries.md`
- Event 事件契约：`event_center_new/docs/schema.md`
- Event 重构说明：`event_center_new/docs/refactor.md`
- Agent 重构方案：`agent_server_new/docs/REFACTOR_PLAN_V2.md`
- Execution API（草案）：`execution_service/docs/api.md`
- Execution 边界：`execution_service/docs/boundaries.md`
- Execution 迁移：`execution_service/docs/migration.md`

## 6. 测试与文档组织约定

当前约定：
- 测试就近放置在各模块下的 `text/` 目录。
- 文档就近放置在各模块下的 `docs/` 目录。

`pytest` 已配置模块级发现路径（`pytest.ini`）：
- `feature_service/text`
- `market_state_engine/text`
- `event_center/text`
- `agent_server/text`（旧模块测试，非新架构验收门槛）
- `execution_service/text`

## 7. 新架构联调最小路径

建议按以下顺序联调：
1. 启动 `feature_service`，验证 `raw-structure/features` 两个接口。
2. 启动 `market_state_engine`，验证对 `feature_service` 的读取与 `status=data_unavailable` 分支。
3. 启动 `event_center_new`，验证事件契约对齐（schema）。
4. 启动 `agent_server_new`，仅通过状态层和事件层输入做决策输出。

## 8. 当前完成度判断（面向新架构）

- `feature_service`：已完成独立运行改造与 ports 注入，契约已冻结，具备下游可消费结构化输出。
- `market_state_engine`：已完成独立骨架与上游短路语义（`data_unavailable`）契约。
- `market_state_engine`：已移除对 feature 层旧契约格式的兼容回退，只接受 `meta + data.raw_market_structure`。
- `event_center_new`：边界定义清晰，事件语义契约已成文，仍需持续按文档收敛命名与输出。
- `agent_server_new`：决策层定位明确，需继续剥离残留状态生成能力，保持只消费状态与事件契约。

---

如果后续需要“对外发布版”的一页文档，建议以本文为主，再拆出：
- 《架构边界白皮书》（面向研发）
- 《服务契约清单》（面向联调）
- 《迁移路线图》（面向迭代管理）
