# execution_service

统一契约入口：`/docs/CONTRACT_INDEX.md`
项目级新架构总览：`/docs/ARCHITECTURE_NEW.md`

`execution_service` 是目标架构中的 **Execution Layer**，位于 `agent_server_new` 下游，负责最终执行裁决与落地。

## 定位

一句话定义：

> `execution_service` 负责把 decision intent 变成可审计的执行结果。

## 职责

1. 接收 `agent_server_new` 的决策意图（direction + confidence + hints）
2. 读取仓位与账户状态
3. 应用硬风控规则（仓位上限、回撤阈值、冷却、频控等）
4. 生成最终执行动作（add/reduce/hold/exit/skip）
5. 可选：路由到交易执行器
6. 输出执行结果与拒绝原因
7. 提供执行回执对账接口（骨架）
8. 回执结果可写回执行状态机终态（filled/canceled/rejected）
9. 回执失败标准化返回 `status=failed`，便于下游统一处理

## 不负责

1. 不做市场状态推断
2. 不做事件中心治理
3. 不做 LLM 语义判断

## 最小目录

```text
execution_service/
  README.md
  TASKS.md
  docs/
    api.md
    boundaries.md
    decision_intent.schema.json
    decision_state.schema.json
    execution_result.schema.json
    execution_signal_result.schema.json
    execution_reconcile_result.schema.json
    retry_meta.schema.json
    risk_policy.schema.json
    schema_mapping.json
    migration.md
  app/
    __init__.py
  domain/
    __init__.py
  adapters/
    __init__.py
  ports/
    execution_sink.py
    position_state_provider.py
    risk_policy_provider.py
  text/
    .gitkeep
```

## 当前阶段

当前为架构骨架阶段：

1. 先冻结职责边界与契约
2. 再接入真实仓位与风控脚本
3. 最后接入交易路由与回执链路

## 契约状态

- `DecisionIntent v1` 已冻结（见 `execution_service/domain/contracts.py`）
- `ExecutionResult v1` 已冻结（见 `execution_service/domain/contracts.py`）
- `DecisionIntent` 已显式包含 `account_id`（默认 `main`）
- `decision_state` 快照已包含 `account_id`，支持按账户追踪执行状态
- 约束：agent 只需提交方向意图与证据提示，不提交仓位上下文
- `Position Context` 由 execution_service 侧读取并用于最终动作裁决

## Providers（当前）

- `PositionStateProvider`：仓位侧输入端口
- `AccountStateProvider`：账户侧输入端口
- 已提供最小 stub：
  - `execution_service/adapters/stub_state_providers.py`
- 已提供 Redis 实现：
  - `execution_service/adapters/redis_state_providers.py`

## 决策引擎（当前）

- `execution_service/domain/decision_engine.py`
- 固定优先级：
  1. 仓位上限
  2. 冷却期
  3. 回撤阈值
  4. 方向冲突

补充：
- 已支持 `hedge` 双向持仓模式（同一 symbol 可多空并存），并按 `long/short` 两条腿分别做仓位上限控制。
- `one_way` 模式保持兼容，仍按方向冲突规则处理。
- `decide` 响应已增加 `signal_result`（模拟信号结构）：`signal_action` + `scope` + `position_before/position_after_simulation`。
- `signal_result` 已增加 `risk_checks`，用于结构化表达账户/仓位/symbol 维度的风控检查结果。
- `risk_checks.check` 已收敛为常量枚举，并由测试强校验与 schema 一致。
- `risk_checks.message_zh` 已冻结为必填字段，统一输出中文检查说明，便于日志与人工排障阅读。
- `risk_checks.scope/status` 已收敛为常量枚举，并由契约测试校验与 schema 一致，降低实现漂移风险。
- `risk_checks.message_zh` 文案模板已收敛为常量定义，避免不同规则输出格式不一致。

## 最小接口（当前）

- `GET /internal/execution/healthz`
- `GET /internal/execution/version`
- `POST /internal/execution/decide`
- `POST /internal/execution/reconcile`
- `GET /internal/execution/debug/state/{exchange}/{symbol}`（联调只读）
- `GET /internal/execution/debug/state/{exchange}/{symbol}?redact=true`（脱敏视图）

## 运行模式

- `EXECUTION_STATE_PROVIDER_MODE=stub|redis`（默认 `stub`）
- 当 `redis` 模式启用时：
  - `EXECUTION_REDIS_URL`（默认 `redis://127.0.0.1:6379/0`）
  - `EXECUTION_POSITION_KEY_TEMPLATE`（默认 `execution:position:{exchange}:{account_id}:{symbol}`）
  - `EXECUTION_ACCOUNT_KEY_TEMPLATE`（默认 `execution:account:{exchange}:{account_id}`）
  - `EXECUTION_RISK_POLICY_KEY_TEMPLATE`（默认 `execution:risk_policy:{exchange}:{symbol}`）
- 执行下沉（可选）：
  - `EXECUTION_SUBMIT_ENABLED=true|false`（默认 `false`）
  - `EXECUTION_SINK_MODE=mock|exchange`（`exchange` 为骨架实现）
  - `EXECUTION_SINK_MOCK_VENUE=mock_exchange`
  - `EXECUTION_SINK_EXCHANGE_VENUE=binance`
  - `EXECUTION_SINK_EXCHANGE_DRY_RUN=true|false`（默认 `true`，建议联调阶段保持开启）
  - `EXECUTION_SINK_EXCHANGE_API_BASE_URL=https://api.binance.com`
  - `EXECUTION_SINK_EXCHANGE_API_KEY` / `EXECUTION_SINK_EXCHANGE_API_SECRET`（`dry_run=false` 必填）
  - `EXECUTION_SINK_EXCHANGE_RECV_WINDOW_MS=5000`
  - `EXECUTION_SINK_EXCHANGE_DEFAULT_ORDER_QTY=0.001`
  - `EXECUTION_SINK_EXCHANGE_TIMEOUT_S=5`
  - `EXECUTION_SUBMIT_MAX_RETRIES`（默认 `0`）
  - `EXECUTION_SUBMIT_BACKOFF_BASE_S`（默认 `0.2`）
  - `EXECUTION_RECONCILE_MAX_RETRIES`（默认 `0`）
  - `EXECUTION_RECONCILE_BACKOFF_BASE_S`（默认 `0.2`）
- 幂等缓存（建议开启）：
  - `EXECUTION_IDEMPOTENCY_ENABLED=true|false`（默认 `true`）
  - `EXECUTION_IDEMPOTENCY_MODE=memory|redis`（默认 `memory`）
  - `EXECUTION_IDEMPOTENCY_REDIS_URL`（当 mode=redis）
  - `EXECUTION_IDEMPOTENCY_KEY_TEMPLATE`（默认 `execution:idempotency:{decision_id}`）
  - `EXECUTION_IDEMPOTENCY_TTL_S`（默认 `3600`）
  - `EXECUTION_IDEMPOTENCY_LOCK_TTL_S`（默认 `30`）
- 执行状态机存储（建议开启）：
  - `EXECUTION_STATE_MACHINE_ENABLED=true|false`（默认 `true`）
  - `EXECUTION_STATE_MACHINE_MODE=memory|redis`（默认 `memory`）
  - `EXECUTION_STATE_MACHINE_REDIS_URL`（当 mode=redis）
  - `EXECUTION_STATE_MACHINE_KEY_TEMPLATE`（默认 `execution:state:{decision_id}`）
  - `EXECUTION_STATE_MACHINE_TTL_S`（默认 `86400`）

## Agent 联调（当前）

- 已提供最小适配器：
  - `execution_service/adapters/agent_execution_plan_adapter.py`
- 用途：把 `agent_server_new` 的 `ExecutionPlan` 映射为 `DecisionIntent v1`

## Redis 集成测试

- 测试文件：`execution_service/text/test_execution_service_redis_ethusdt.py`
- 说明：使用 `binance/ETHUSDT` 的 execution 键数据做端到端裁决验证（`integration` 标记）
- Redis 键契约：`execution_service/docs/redis_keys.md`
- cURL 示例：`execution_service/docs/curl_examples.md`
- HTTPie 示例：`execution_service/docs/httpie_examples.md`
- decision_state schema：`execution_service/docs/decision_state.schema.json`
- decision_intent schema：`execution_service/docs/decision_intent.schema.json`
- execution_result schema：`execution_service/docs/execution_result.schema.json`
- execution_signal_result schema：`execution_service/docs/execution_signal_result.schema.json`
- execution_reconcile_result schema：`execution_service/docs/execution_reconcile_result.schema.json`
- retry_meta schema：`execution_service/docs/retry_meta.schema.json`
- risk_policy schema：`execution_service/docs/risk_policy.schema.json`
- `execution_result/execution_reconcile_result` 中的 `retry_meta` 已统一通过 `$ref` 引用独立 schema，避免枚举漂移
- schema mapping 清单：`execution_service/docs/schema_mapping.json`
- `schema_mapping.json` 已登记 `RetryMeta` 的 `$ref` 引用来源，守卫会校验引用路径和值不漂移
- `DecisionIntent/ExecutionResult` 的关键枚举与边界也已纳入 `schema_mapping.references` 机器校验
- `ExecutionReconcileResult` 也已纳入 `schema_mapping`，关键状态/错误码与 `retry_meta` 引用受守卫保护
- `ExchangeExecutionSink` 已支持 dry-run 请求快照与 Binance 签名请求骨架（真实请求需显式关闭 dry-run）
- `ExchangeExecutionSink.reconcile` 已支持 Binance 状态映射到标准状态（并返回 `exchange_status_raw`）
- `ExchangeExecutionSink.reconcile` 的 `avg_price` 已支持多源回退计算（`avgPrice`/`cummulativeQuoteQty÷executedQty`/`price`）
- execution 内部作用域已引入 `account_id`（当前默认 `main`），为未来多账户扩展预留兼容位
