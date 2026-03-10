# UTaker 联调契约速查（新架构）

更新时间：2026-03-09
统一契约入口：`docs/CONTRACT_INDEX.md`

## 1. 服务调用顺序

```text
feature_service -> market_state_engine -> agent_server_new
feature_service -> event_center_new
agent_server_new -> execution_service
```

事件流冻结约定：

1. 结构事件通道  
`event_center_new(结构事件) -> market_state_engine -> agent_server_new`

2. 外部事件通道  
`event_center_new(舆情/链上/新闻等) -> agent_server_new`

约束：
- `market_state_engine` 只做市场结构状态分析，不直接处理舆情/链上/新闻事件流。

## 2. feature_service

### 2.1 健康检查
- `GET /internal/feature-service/healthz`

### 2.2 原始结构（给状态层）
- `GET /internal/feature-service/raw-structure/{exchange}/{symbol}`
- 成功响应：`{ meta, data }`
- 关键字段：
  - `meta.schema_version`
  - `meta.generated_at_ms`
  - `meta.degraded`
  - `meta.degraded_reasons`
  - `data.exchange`
  - `data.symbol`
  - `data.raw_market_structure`
- 说明：仅支持新契约读取路径 `data.raw_market_structure`，不再支持旧格式。

### 2.3 特征快照（给事件层/状态层）
- `GET /internal/feature-service/features/{exchange}/{symbol}`
- 成功响应：`{ meta, data }`
- 关键字段：
  - `data.indicators`
  - `data.derived_metrics`
  - `data.structure_snapshot`

### 2.4 错误码
- `503` + `detail.code=feature_data_unavailable`
- `detail.degraded_reasons`：上游降级原因列表

## 3. market_state_engine

### 3.1 健康检查
- `GET /internal/market-state/healthz`

### 3.2 状态查询
- `GET /internal/market-state/{exchange}/{symbol}`
- 关键字段：
  - `exchange`
  - `symbol`
  - `status`（`ok` / `data_unavailable`）
  - `msl`
  - `state_features`
  - `anomaly_flags`
  - `raw_market_structure`
  - `ts`

### 3.3 上游不可用时约定
- 当 feature 层返回 `503 feature_data_unavailable`：
  - 状态层返回 `HTTP 200`
  - `status=data_unavailable`
  - `reason_code=feature_data_unavailable`
  - `degraded_reasons` 透传

## 4. event_center_new（事件语义）

当前冻结方向（用于联调字段对齐）：
- Event 基础对象：`EventEnvelope`
- 证据对象：`Evidence`
- 输出方向：`SelectedEvent` / `EventBatch`

建议最小字段（跨服务对齐）：
- `id`
- `ts_ms`
- `asset`
- `type`
- `source_category`
- `importance`
- `ttl_ms`
- `payload`
- `trace`

## 5. agent_server_new（输入要求）

决策层应消费：
- 来自事件层：`signal_event`、`active_events`
- 来自状态层：`MSL`、`key_features`、`anomaly_flags`
- 约束：`MSL` 按结构字段白名单解析，不依赖 `sentiment_state` 等已下线字段

决策层推荐输入顺序（冻结）：
- `MSL -> Key Evidence -> Active Events -> Signal Event`

执行层应消费：
- 来自持仓上下文：`position_context`
- 来自决策层：`ExecutionPlan` / direction intent / risk hints
- 接口：`POST /internal/execution/decide`

决策层输出：
- `ExecutionPlan`
- `DecisionTrace`

## 6. execution_service（草案）

执行层目标输入：
- `decision_id`
- `exchange`
- `account_id`
- `symbol`
- `direction_intent`
- `confidence`
- `cross_horizon_policy`
- `risk_hints`

执行层目标输出：
- `execution_action`
- `reject_reason`
- `applied_risk_rules`
- `order_result`（可选）
- `signal_result`（模拟信号结构）

执行层新增回执对账接口（骨架）：
- `POST /internal/execution/reconcile`

执行层状态来源：
- 支持 `stub` 与 `redis` 双模式（`EXECUTION_STATE_PROVIDER_MODE`）

执行层冻结 Schema：
- `execution_service/docs/decision_intent.schema.json`
- `execution_service/docs/execution_result.schema.json`
- `execution_service/docs/execution_signal_result.schema.json`
- `execution_service/docs/decision_state.schema.json`
- `execution_service/docs/execution_reconcile_result.schema.json`
- `execution_service/docs/retry_meta.schema.json`
- `execution_service/docs/risk_policy.schema.json`
- `execution_service/docs/schema_mapping.json`
- `docs/CONTRACT_INDEX.md` 中 `execution_schema_mapping_version` 必须与 `/internal/execution/version` 一致

## 7. 联调判定清单（最小）

1. `feature_service` 两个业务接口都返回 `meta + data`。
2. `market_state_engine` 能读取 `feature_service.data.raw_market_structure`。
3. 当 feature 层返回 `503` 时，状态层正确返回 `status=data_unavailable`。
4. `agent_server_new` 不直接读取 raw market structure。

## 8. 文档入口

- 总览：`ARCHITECTURE_NEW.md`
- 契约索引：`CONTRACT_INDEX.md`
- 迁移执行清单：`REFACTOR_PLAYBOOK_NEW.md`
- cURL 示例：`CONTRACTS_CURL_EXAMPLES.md`
- HTTPie 示例：`CONTRACTS_HTTPIE_EXAMPLES.md`
- 一键冒烟脚本：`scripts/integration_smoke_new_arch.sh`
- 契约守卫脚本（CI 可用）：`scripts/check_feature_contract_guard.sh`
- Feature Schema 守卫脚本（CI 可用）：`scripts/check_feature_service_schema_guard.sh`
- State Engine 守卫脚本（CI 可用）：`scripts/check_market_state_engine_guard.sh`
- State->Agent 联动守卫脚本（CI 可用）：`scripts/check_state_to_agent_contract_guard.sh`
- Runner 输出 Schema 守卫脚本（CI 可用）：`scripts/check_runner_output_schema_guard.sh`
- Contract Docs Index 守卫脚本（CI 可用）：`scripts/check_contract_docs_index_guard.sh`
- Agent->Execution 联动守卫脚本（CI 可用）：`scripts/check_agent_to_execution_guard.sh`
- 新架构守卫总入口（CI 可用）：`scripts/check_new_arch_guards.sh`
- 仅跑 event_center quick：`scripts/check_new_arch_guards.sh --event-center-quick`
- 仅跑 event_center 全量：`scripts/check_new_arch_guards.sh --event-center-only`
- 顶层入口接线策略可选：追加 `--lenient-wiring`（默认 `--strict-wiring`）
- Feature API：`feature_service/docs/api.md`
- State API：`market_state_engine/docs/api.md`
- Event Schema：`event_center_new/docs/schema.md`
- Agent 重构方案：`agent_server_new/docs/REFACTOR_PLAN_V2.md`
- Agent runner 输出契约：`agent_server_new/docs/runner_output_contract.md`
- Agent runner 输出 Schema：`agent_server_new/docs/runner_output.schema.json`
- Execution API（草案）：`execution_service/docs/api.md`
- Execution DecisionIntent Schema：`execution_service/docs/decision_intent.schema.json`
- Execution ExecutionResult Schema：`execution_service/docs/execution_result.schema.json`
- Execution SignalResult Schema：`execution_service/docs/execution_signal_result.schema.json`
- Execution DecisionState Schema：`execution_service/docs/decision_state.schema.json`
- Execution ReconcileResult Schema：`execution_service/docs/execution_reconcile_result.schema.json`
- Execution RetryMeta Schema：`execution_service/docs/retry_meta.schema.json`
- Execution RiskPolicy Schema：`execution_service/docs/risk_policy.schema.json`
- Execution Schema Mapping：`execution_service/docs/schema_mapping.json`
- Execution cURL 示例：`execution_service/docs/curl_examples.md`
- Execution HTTPie 示例：`execution_service/docs/httpie_examples.md`
- Execution Redis 键契约：`execution_service/docs/redis_keys.md`
