# execution_service API（草案）

## 健康检查

- `GET /internal/execution/healthz`

返回示例：

```json
{
  "ok": true,
  "service": "execution_service"
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
  "schema_mapping_version": "execution-schema-mapping-v2",
  "ts": 1760000000000
}
```

## 执行裁决

- `POST /internal/execution/decide`

请求示例：

```json
{
  "decision_id": "dec-001",
  "exchange": "binance",
  "symbol": "ETHUSDT",
  "direction_intent": "long",
  "confidence": {"level": "medium", "score": 0.67},
  "cross_horizon_policy": {"suggested_policy": "reduce_risk"},
  "risk_hints": {"market_fragility": "medium"},
  "trace_id": "trace-20260310-001"
}
```

输入契约（DecisionIntent v1）：

1. `decision_id`: 非空字符串
2. `exchange`: 非空字符串
3. `symbol`: 非空字符串
4. `direction_intent`: `long | short | none`
5. `confidence.level`: `low | medium | high`
6. `confidence.score`: `[0, 1]` 浮点数
7. `cross_horizon_policy`: 对象（可为空对象）
8. `risk_hints`: 对象（可为空对象）
9. `trace_id`: 可选字符串
10. JSON Schema：`execution_service/docs/decision_intent.schema.json`

响应示例：

```json
{
  "decision_id": "dec-001",
  "execution_action": "hold",
  "reject_reason": "position_limit_reached",
  "applied_risk_rules": ["max_position_limit"],
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
7. JSON Schema：`execution_service/docs/execution_result.schema.json`

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

建议标准拒绝码（首批冻结）：

- `position_limit_reached`
- `cooldown_active`
- `max_drawdown_exceeded`
- `direction_conflict_with_position`

## 调试状态快照

- `GET /internal/execution/debug/state/{exchange}/{symbol}?redact=true|false&decision_id=...`
- `decision_state` JSON Schema：`execution_service/docs/decision_state.schema.json`

返回示例：

```json
{
  "exchange": "binance",
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
  - `status`: 当前状态
  - `last_transition`: 最近一次状态跃迁
  - `attempts`: submit 尝试次数（未 submit 为 `0`）
  - `submitted_at_ms`: 最近一次成功 submit 时间戳（未 submit 为 `null`）
  - `last_error`: 最近一次 submit 错误文本（无错误为空字符串）
  - `source`: 产出状态的服务标识（当前固定 `execution_service`）
  - `trace_id`: 透传的链路追踪 ID（若请求未提供则为 `null`）
- 状态机跃迁规则（冻结）：
  - `pending -> pending/submitted/failed/skipped/decided`
  - `submitted/failed/skipped/decided` 为终态，仅允许保持原状态
  - 非法跃迁会被拒绝并记录中文告警日志，不覆盖已存终态

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
- `EXECUTION_SUBMIT_MAX_RETRIES`
- `EXECUTION_SUBMIT_BACKOFF_BASE_S`
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

## Schema 与字段来源映射

机器可校验清单：`execution_service/docs/schema_mapping.json`

| 语义对象 | 关键字段 | Schema 文件 | 代码定义位置 | Owner | Change Policy |
| --- | --- | --- | --- | --- | --- |
| DecisionIntent | `decision_id` `exchange` `symbol` `direction_intent` `confidence` `cross_horizon_policy` `risk_hints` `trace_id` | `execution_service/docs/decision_intent.schema.json` | `execution_service/domain/contracts.py` `DecisionIntent` | `execution_service` | `breaking` |
| ExecutionResult | `decision_id` `execution_action` `reject_reason` `applied_risk_rules` `order_result` `notes` | `execution_service/docs/execution_result.schema.json` | `execution_service/domain/contracts.py` `ExecutionResult` | `execution_service` | `breaking` |
| DecisionState | `status` `last_transition` `attempts` `submitted_at_ms` `last_error` `source` `trace_id` `updated_at_ms` | `execution_service/docs/decision_state.schema.json` | `execution_service/app/service.py` `_save_state` 与状态写入逻辑 | `execution_service` | `non_breaking` |

说明：
- schema 用于契约冻结与守卫检查。
- 代码定义位置用于评审时追溯字段来源与语义变更点。
- `owner/change_policy` 由 `schema_mapping.json` 统一管理并由测试强校验。
- `schema_mapping.json.version` 必须与 `/internal/execution/version.schema_mapping_version` 保持一致。
