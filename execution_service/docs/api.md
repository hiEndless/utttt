# execution_service API（草案）

## 健康检查

- `GET /internal/execution/healthz`

返回示例：

```json
{
  "ok": true,
  "service": "execution_service",
  "ts": 1760000000000,
  "ts_ms": 1760000000000
}
```

## 版本信息

- `GET /internal/execution/version`

返回示例：

```json
{
  "service": "execution_service",
  "contract_version": "execution-contract-v1",
  "ruleset_version": "risk-rules-v1",
  "state_machine_version": "execution-state-machine-v1",
  "idempotency_version": "execution-idempotency-v1",
  "schema_mapping_version": "execution-schema-mapping-v9",
  "ts": 1760000000000,
  "ts_ms": 1760000000000
}
```

## 执行裁决

- `POST /internal/execution/decide`

请求示例：

```json
{
  "decision_id": "dec-001",
  "exchange": "binance",
  "account_id": "main",
  "symbol": "ETHUSDT",
  "direction_intent": "long",
  "confidence": {"level": "medium", "score": 0.67},
  "decision_confidence": {"level": "medium", "score": 0.67},
  "cross_horizon_policy": {"suggested_policy": "reduce_risk"},
  "risk_hints": {"market_fragility": "medium"},
  "trace_id": "trace-20260310-001"
}
```

输入契约（DecisionIntent v1）：

1. `decision_id`: 非空字符串
2. `exchange`: 非空字符串
3. `account_id`: 非空字符串（当前默认建议 `main`）
4. `symbol`: 非空字符串
5. `direction_intent`: `long | short | none`
6. `confidence.level`: `low | medium | high`
7. `confidence.score`: `[0, 1]` 浮点数
8. `decision_confidence`: 可选，语义别名（若与 `confidence` 同时出现，必须一致）
9. `cross_horizon_policy`: 对象（可为空对象）
10. `risk_hints`: 对象（可为空对象）
11. `trace_id`: 可选字符串
12. JSON Schema：`execution_service/docs/decision_intent.schema.json`

一致性约束：
- 同时提供 `confidence` 与 `decision_confidence` 时，若数值不一致，请求将返回 `400`，避免语义错位。

响应示例：

```json
{
  "decision_id": "dec-001",
  "execution_action": "hold",
  "reject_reason": "position_limit_reached",
  "applied_risk_rules": ["max_position_limit"],
  "policy_snapshot": {"policy_version": "risk-policy-default-v1", "ruleset_hash": "risk-rules-v1"},
  "notes": "当前仓位已达上限"
}
```

输出契约（ExecutionResult v1）：

1. `decision_id`: 非空字符串
2. `execution_action`: `add | reduce | hold | exit | skip`
3. `reject_reason`: 可选字符串（拒绝/降级时建议填写标准码）
4. `applied_risk_rules`: 字符串数组
5. `order_result`: 可选对象（真实下单后回填）
6. `notes`: 可选字符串（中文解释）
7. `signal_result`: 可选对象（执行层模拟信号结构，当前默认返回）
8. `policy_snapshot`: 可选对象（当前生效策略快照：`policy_version/ruleset_hash`）
9. JSON Schema：`execution_service/docs/execution_result.schema.json`

说明：
- 当 `EXECUTION_SUBMIT_ENABLED=true` 且动作为 `add/reduce/exit` 时，服务会尝试调用 `ExecutionSink.submit(...)` 回填 `order_result`。
- submit 支持重试（指数退避）：
  - 最大尝试次数：`1 + EXECUTION_SUBMIT_MAX_RETRIES`
  - 退避基数秒：`EXECUTION_SUBMIT_BACKOFF_BASE_S`
  - `order_result.retry_meta` 会记录尝试次数与状态。
- 下沉失败时会降级为：
  - `execution_action=skip`
  - `reject_reason=execution_submit_failed`
  - `applied_risk_rules` 追加 `execution_submit_fallback`
- 当幂等缓存启用时（默认开启），相同 `decision_id` 的重复请求会直接返回首次结果，不重复 submit。
- 当同一 `decision_id` 正在处理中且未拿到锁时，返回：
  - `execution_action=skip`
  - `reject_reason=idempotency_in_progress`
  - `applied_risk_rules` 包含 `idempotency_lock_busy`
- `signal_result`（模拟结构）字段说明：
  - `signal_action`: `add_long|add_short|reduce_long|reduce_short|hold|skip|exit_all`
  - `risk_state`: `normal|warn|reduce_only|frozen`
    - 风险状态包含前态记忆与降级防抖：上一拍为 `frozen/reduce_only` 时，本拍即使规则压力消失，也先过渡到 `warn`，避免状态抖动
    - Redis `account_state.risk_state` 非法值会自动归一化为 `normal`
    - Stub `account_state.risk_state` 也采用相同归一化规则，保证多运行模式一致
    - `risk_state` 枚举由代码常量单点维护，并通过契约测试校验与 schema 一致
    - `risk_state`（含 `previous/current_risk_state`）在 schema 层通过 `$ref` 复用独立定义：`execution_service/docs/risk_state.schema.json`
  - `mode`: 当前固定 `simulated`
  - `scope/position_before/position_after_simulation` 在 schema 层通过 `$ref` 复用独立定义：
    - `execution_service/docs/signal_scope.schema.json`
    - `execution_service/docs/position_before.schema.json`
    - `execution_service/docs/position_after_simulation.schema.json`
  - `signal_action` 在 schema 层通过 `$ref` 复用独立定义：`execution_service/docs/signal_action.schema.json`
  - `mode` 在 schema 层通过 `$ref` 复用独立定义：`execution_service/docs/signal_mode.schema.json`
  - `risk_checks` 在 schema 层通过 `$ref` 复用独立定义：`execution_service/docs/risk_checks.schema.json`
  - `rule_priority_order` 在 schema 层通过 `$ref` 复用独立定义：`execution_service/docs/rule_priority_order.schema.json`
  - `position_mode` 在 schema 层通过 `$ref` 复用独立定义：`execution_service/docs/position_mode.schema.json`
  - `decision_state.status/last_transition` 在 schema 层通过 `$ref` 复用独立定义：`execution_service/docs/decision_state_status.schema.json`
  - `execution_result/decision_state.execution_action` 在 schema 层通过 `$ref` 复用独立定义：`execution_service/docs/execution_action.schema.json`
  - `execution_result/decision_state.reject_reason` 在 schema 层通过 `$ref` 复用独立定义：`execution_service/docs/reject_reason.schema.json`
  - `execution_result/decision_state.policy_snapshot` 在 schema 层通过 `$ref` 复用独立定义：`execution_service/docs/policy_snapshot.schema.json`
  - `scope`: `exchange/account_id/symbol`
  - `position_before`: 模拟前仓位快照（long/short/net）
  - `position_after_simulation`: 按步长模拟后的仓位快照（long/short/net）
  - `risk_checks`: 结构化风控检查明细（账户/仓位/symbol 维度）
    - `check` 枚举（冻结）：`account_drawdown_limit`、`account_available_balance`、`account_notional_limit`、`account_margin_ratio_limit`、`account_daily_loss_limit`、`account_consecutive_loss_limit`、`symbol_exposure_ratio`、`long_leg_position_limit`、`short_leg_position_limit`
    - `scope/status` 枚举（冻结）：`account|symbol|position` 与 `pass|fail`
    - `message_zh`：必填中文说明，包含当前值与阈值，便于值班排障与联调定位；文案模板由代码常量统一维护
    - 生成实现：`risk_checks` 由独立 builder 统一构造，保证裁决逻辑与检查项生成逻辑解耦
  - `signal_result` 组装由独立 result builder 统一处理，确保 `signal_action/scope/position_after_simulation` 结构稳定
  - `rule_debug`（可选调试字段）：
    - `hit_rule`：命中的规则名（未命中时为 `passed_all_rules/none_intent/dual_side_hedge_mode` 等流程标识）
    - `rule_priority_order`：本次裁决实际使用的规则优先级顺序
    - `hit_rule_value/hit_rule_threshold`：命中规则的值与阈值（如适用）
    - `previous_risk_state/current_risk_state`：风险状态迁移审计字段（前态 -> 当前态）
    - `risk_state_changed`：布尔值，表示本次是否发生风险状态迁移
    - `risk_state_change_reason`：标准原因码（`reject_frozen|reject_reduce_only|pressure_warn|hysteresis_soften|default_normal`）
    - `risk_state_change_reason_zh`：与原因码对应的中文解释
    - 以上原因码与中文解释由代码常量单点维护，并通过契约测试校验与 schema 一致
    - `risk_state_change_reason(_zh)` 在 schema 层通过 `$ref` 复用独立定义：`execution_service/docs/risk_state_change_reason.schema.json`
    - `rule_debug` 在 schema 层通过 `$ref` 复用独立定义：`execution_service/docs/rule_debug.schema.json`
    - `matched_at_ms`：本次规则命中时间戳（毫秒）
    - `evaluation_trace`：按规则顺序记录每条规则的 `order`、`scope`、`pass/fail`、`value/threshold` 与 `note_zh`
      - `evaluation_trace` 在 schema 层通过 `$ref` 复用独立定义：`execution_service/docs/evaluation_trace.schema.json`
  - `policy_snapshot`: 当前裁决生效策略快照
    - `policy_version`: 风控策略版本（来自 `risk_policy.policy_version`，缺省回退 `risk-policy-default-v1`）
    - `ruleset_hash`: 规则集版本/哈希（来自 `risk_policy.ruleset_hash`，缺省回退 `risk-rules-v1`）
  - 规则优先级为默认冻结顺序：`position_limit -> cooldown -> max_drawdown -> account_notional -> margin_ratio -> daily_loss -> consecutive_loss -> direction_conflict`
    - 可选覆盖：`risk_policy.rule_priority_order`（必须提供八项完整排列，否则自动回退默认）

建议标准拒绝码（首批冻结）：

- `position_limit_reached`
- `cooldown_active`
- `max_drawdown_exceeded`
- `account_notional_exceeded`
- `account_margin_ratio_exceeded`
- `daily_loss_exceeded`
- `consecutive_loss_exceeded`
- `direction_conflict_with_position`

## 执行回执对账（骨架）

- `POST /internal/execution/reconcile`
- JSON Schema：`execution_service/docs/execution_reconcile_result.schema.json`

请求示例：

```json
{
  "order_id": "mock-order-001",
  "decision_id": "dec-001",
  "exchange": "binance",
  "account_id": "main",
  "symbol": "ETHUSDT"
}
```

响应示例（mock）：

```json
{
  "mode": "mock",
  "venue": "mock_exchange",
  "order_id": "mock-order-001",
  "decision_id": "dec-001",
  "account_id": "main",
  "exchange": "binance",
  "symbol": "ETHUSDT",
  "status": "filled",
  "filled_qty": 1.0,
  "avg_price": 1000.0,
  "retry_meta": {"attempts": 1, "max_retries": 0, "status": "ok"},
  "ts": 1760000000000
}
```

响应示例（失败标准化输出）：

```json
{
  "mode": "mock",
  "order_id": "mock-order-err-001",
  "status": "failed",
  "reason_code": "reconcile_non_retryable_error",
  "error_message": "invalid_order_id",
  "idempotency_hit": false,
  "retry_meta": {"attempts": 1, "max_retries": 3, "status": "failed", "retryable": false},
  "ts": 1760000000002
}
```

错误约定：
- `400`: `order_id` 缺失
- `503`: `execution_sink_not_configured`
- `501`: `execution_sink_reconcile_not_supported`

说明：
- 当 payload 或回执中携带 `decision_id` 且回执状态可识别时，服务会写回 `decision_state`（例如 `submitted -> filled`）。
- `reconcile` 已接入 `order_id` 幂等：相同 `order_id` 二次调用优先返回缓存结果，并标记 `idempotency_hit=true`。
- `reconcile` 支持错误分级重试：可重试错误会按指数退避重试，并在响应 `retry_meta` 中记录尝试轨迹。
- 对账失败场景返回业务响应 `status=failed`（HTTP 200），减少下游对 502 的分支处理。
- `reason_code` 枚举由 `execution_service/domain/reconcile_codes.py` 单点定义，并由测试校验与 schema 一致。
- `status` 枚举由 `execution_service/domain/reconcile_statuses.py` 单点定义，并由测试校验与 schema 一致。
- `retry_meta.status` 枚举由 `execution_service/domain/retry_meta.py` 单点定义，并由测试校验两份 schema 一致。
- `retry_meta` 独立 schema：`execution_service/docs/retry_meta.schema.json`
- `execution_result.schema.json` 与 `execution_reconcile_result.schema.json` 通过 `$ref` 统一引用 `retry_meta.schema.json`。

## 调试状态快照

- `GET /internal/execution/debug/state/{exchange}/{symbol}?redact=true|false&decision_id=...`
  - 可选：`account_id`（默认 `main`）
- `decision_state` JSON Schema：`execution_service/docs/decision_state.schema.json`

返回示例：

```json
{
  "exchange": "binance",
  "account_id": "main",
  "symbol": "ETHUSDT",
  "position_state": {
    "position_side": "flat",
    "position_size": 0.1,
    "max_position_size": 1.0,
    "cooldown_seconds_left": 0
  },
  "account_state": {
    "account_equity": 10000,
    "available_balance": 9000,
    "max_drawdown_ratio": 0.2,
    "current_drawdown_ratio": 0.01
  },
  "risk_policy": {
    "max_position_size": 1.0,
    "max_drawdown_ratio": 0.2
  },
  "redacted": false,
  "ts": 1760000000000
}
```

说明：
- `redact=true` 时会脱敏敏感字段（如 `account_equity/available_balance/unrealized_pnl`）
- 传入 `decision_id` 时返回 `decision_state`，用于查看状态机快照（`pending/submitted/failed/skipped/decided`）
- `decision_state` 当前包含：
  - `account_id`: 账户作用域标识（当前默认 `main`）
  - `status`: 当前状态
  - `last_transition`: 最近一次状态跃迁
  - `attempts`: submit 尝试次数（未 submit 为 `0`）
  - `submitted_at_ms`: 最近一次成功 submit 时间戳（未 submit 为 `null`）
  - `last_error`: 最近一次 submit 错误文本（无错误为空字符串）
  - `risk_state`: 最近一次裁决风险状态（`normal|warn|reduce_only|frozen`）
  - `rule_debug`: 最近一次裁决命中规则调试信息（命中规则名/规则顺序/值阈值/命中时间戳/逐条评估轨迹中文说明）
  - `source`: 产出状态的服务标识（当前固定 `execution_service`）
  - `trace_id`: 透传的链路追踪 ID（若请求未提供则为 `null`）
  - `policy_snapshot`: 最近一次裁决生效策略快照（`policy_version/ruleset_hash`）
  - `reconcile_order_id`: 最近一次回执对账的订单号（如有）
  - `reconcile_status_raw`: 最近一次回执原始状态（如有）
- 状态机跃迁规则（冻结）：
  - `pending -> pending/submitted/failed/skipped/decided`
  - `submitted -> submitted/filled/canceled/rejected/failed`
  - `failed/skipped/decided/filled/canceled/rejected` 为终态，仅允许保持原状态
  - 非法跃迁会被拒绝并记录中文告警日志，不覆盖已存终态

## Confidence 迁移指标

- `GET /internal/execution/debug/confidence-metrics`

返回示例：

```json
{
  "service": "execution_service",
  "confidence_migration_metrics": {
    "decide_requests_total": 3,
    "confidence_only_requests": 1,
    "decision_confidence_requests": 2,
    "confidence_alias_mismatch_rejections": 1
  },
  "ts": 1760000000000,
  "ts_ms": 1760000000000
}
```

指标说明：
- `decide_requests_total`: `/decide` 请求总数（进程内计数）。
- `confidence_only_requests`: 仅提供 `confidence`（未提供 `decision_confidence`）的请求数。
- `decision_confidence_requests`: 提供 `decision_confidence` 的请求数（可同时带 `confidence`）。
- `confidence_alias_mismatch_rejections`: 因双字段不一致被拒绝（400）的次数。
- 当前为进程内内存指标，重启后清零；用于迁移阶段联调观察，不作为长期计费/审计指标。

## 状态提供器模式

`execution_service` 支持两种运行模式：

1. `stub`（默认）：使用内置 stub 状态
2. `redis`：从 Redis 读取仓位/账户/策略状态

环境变量：

- `EXECUTION_STATE_PROVIDER_MODE=stub|redis`
- `EXECUTION_REDIS_URL`
- `EXECUTION_POSITION_KEY_TEMPLATE`
- `EXECUTION_ACCOUNT_KEY_TEMPLATE`
- `EXECUTION_RISK_POLICY_KEY_TEMPLATE`
- `EXECUTION_SUBMIT_ENABLED`
- `EXECUTION_SINK_MODE`
- `EXECUTION_SINK_MOCK_VENUE`
- `EXECUTION_SINK_EXCHANGE_VENUE`（当 `EXECUTION_SINK_MODE=exchange`）
- `EXECUTION_SINK_EXCHANGE_DRY_RUN`（默认 `true`）
- `EXECUTION_SINK_EXCHANGE_API_BASE_URL`
- `EXECUTION_SINK_EXCHANGE_API_KEY`
- `EXECUTION_SINK_EXCHANGE_API_SECRET`
- `EXECUTION_SINK_EXCHANGE_RECV_WINDOW_MS`
- `EXECUTION_SINK_EXCHANGE_DEFAULT_ORDER_QTY`
- `EXECUTION_SINK_EXCHANGE_TIMEOUT_S`
- `EXECUTION_SUBMIT_MAX_RETRIES`
- `EXECUTION_SUBMIT_BACKOFF_BASE_S`
- `EXECUTION_RECONCILE_MAX_RETRIES`
- `EXECUTION_RECONCILE_BACKOFF_BASE_S`
- `EXECUTION_IDEMPOTENCY_ENABLED`
- `EXECUTION_IDEMPOTENCY_MODE`
- `EXECUTION_IDEMPOTENCY_REDIS_URL`
- `EXECUTION_IDEMPOTENCY_KEY_TEMPLATE`
- `EXECUTION_IDEMPOTENCY_TTL_S`
- `EXECUTION_IDEMPOTENCY_LOCK_TTL_S`
- `EXECUTION_STATE_MACHINE_ENABLED`
- `EXECUTION_STATE_MACHINE_MODE`
- `EXECUTION_STATE_MACHINE_REDIS_URL`
- `EXECUTION_STATE_MACHINE_KEY_TEMPLATE`
- `EXECUTION_STATE_MACHINE_TTL_S`

补充说明（exchange sink）：
- `dry_run=true` 时，`submit/reconcile` 不会请求真实交易所，会在返回结果中提供 `request` 快照用于联调核对。
- `dry_run=false` 时，当前提供 Binance 签名请求骨架（`POST/GET /api/v3/order`），网络或鉴权异常将由 submit/reconcile 重试与降级逻辑统一处理。
- `reconcile` 会将 Binance 原始状态映射为标准 `status`：
  - `FILLED -> filled`
  - `CANCELED/CANCELLED/EXPIRED/EXPIRED_IN_MATCH -> canceled`
  - `REJECTED -> rejected`
  - 其他状态回退 `submitted`
- 对账返回会附加 `exchange_status_raw`，便于联调定位状态映射行为。
- `reconcile.avg_price` 计算优先级：
  - 1) `avgPrice`
  - 2) `cummulativeQuoteQty / executedQty`
  - 3) `price`

补充说明（account scope）：
- execution 读取仓位/账户状态时已支持 `account_id` 作用域（当前默认 `main`）。
- Redis 默认 key 模板已包含 `{account_id}`，但也兼容自定义模板（可按需回退到旧模板）。

补充说明（双向持仓）：
- 风控已支持 `hedge` 模式（同 symbol 多空双开），可通过以下字段表达：
  - 仓位状态：`position_mode=hedge`、`long_position_size`、`short_position_size`
  - 风控策略：`allow_dual_side=true`、`max_long_position_size`、`max_short_position_size`
  - 账户策略：`min_available_balance`、`max_symbol_exposure_ratio`、`max_account_notional`、`max_margin_ratio`、`max_daily_loss`、`max_consecutive_loss_count`、`simulation_step_size`
  - 规则优先级策略：`rule_priority_order`（可选覆盖，必须是八项完整排列）

## Schema 与字段来源映射

机器可校验清单：`execution_service/docs/schema_mapping.json`

| 语义对象 | 关键字段 | Schema 文件 | 代码定义位置 | Owner | Change Policy |
| --- | --- | --- | --- | --- | --- |
| DecisionIntent | `decision_id` `exchange` `account_id` `symbol` `direction_intent` `confidence` `decision_confidence` `cross_horizon_policy` `risk_hints` `trace_id` | `execution_service/docs/decision_intent.schema.json` | `execution_service/domain/contracts.py` `DecisionIntent` | `execution_service` | `breaking` |
| ExecutionResult | `decision_id` `execution_action` `reject_reason` `applied_risk_rules` `order_result` `signal_result` `policy_snapshot` `notes` | `execution_service/docs/execution_result.schema.json` | `execution_service/domain/contracts.py` `ExecutionResult` | `execution_service` | `breaking` |
| DecisionState | `account_id` `status` `last_transition` `attempts` `submitted_at_ms` `last_error` `policy_snapshot` `source` `trace_id` `updated_at_ms` | `execution_service/docs/decision_state.schema.json` | `execution_service/app/service.py` `_save_state` 与状态写入逻辑 | `execution_service` | `non_breaking` |
| RiskPolicy | `max_position_size` `max_long_position_size` `max_short_position_size` `max_drawdown_ratio` `position_mode` `allow_dual_side` `min_available_balance` `max_symbol_exposure_ratio` `max_account_notional` `max_margin_ratio` `max_daily_loss` `max_consecutive_loss_count` `simulation_step_size` `rule_priority_order` | `execution_service/docs/risk_policy.schema.json` | `execution_service/adapters/redis_state_providers.py` `RedisRiskPolicyProvider` | `execution_service` | `non_breaking` |

说明：
- schema 用于契约冻结与守卫检查。
- 代码定义位置用于评审时追溯字段来源与语义变更点。
- `owner/change_policy` 由 `schema_mapping.json` 统一管理并由测试强校验。
- `schema_mapping.json.last_updated` 表示 mapping 最近更新时间（`YYYY-MM-DD`）。
- `schema_mapping.json.version` 必须与 `/internal/execution/version.schema_mapping_version` 保持一致。
- `schema_mapping.json.last_updated` 必须等于 `docs/CONTRACT_INDEX.md` 的“更新时间”。
- 若 `change_policy=breaking` 的对象发生变更，`schema_mapping.version` 主版本号必须递增（守卫强校验）。
- breaking 变更检测包含 schema 文件内容 hash 变化（不仅是 mapping 字段变化）。
- 升版守卫失败时会输出触发对象与原因（新增对象/签名变更/schema hash 变更）。
