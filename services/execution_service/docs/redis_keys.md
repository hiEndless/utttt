# execution_service Redis Key 契约

更新时间：2026-03-10

当 `EXECUTION_STATE_PROVIDER_MODE=redis` 时，execution_service 读取以下键：

## 1) 仓位状态

- key 模板：`execution:position:{exchange}:{account_id}:{symbol}`
- 默认示例：`execution:position:binance:main:ETHUSDT`

value(JSON)：

```json
{
  "position_mode": "one_way",
  "position_side": "flat",
  "position_size": 0.1,
  "long_position_size": 0.0,
  "short_position_size": 0.0,
  "max_position_size": 1.0,
  "unrealized_pnl": 0.0,
  "cooldown_seconds_left": 0
}
```

## 2) 账户状态

- key 模板：`execution:account:{exchange}:{account_id}`
- 默认示例：`execution:account:binance:main`

value(JSON)：

```json
{
  "account_equity": 10000.0,
  "available_balance": 9000.0,
  "margin_ratio": 0.1,
  "max_drawdown_ratio": 0.2,
  "current_drawdown_ratio": 0.01
}
```

## 3) 风控策略

- key 模板：`execution:risk_policy:{exchange}:{symbol}`
- 默认示例：`execution:risk_policy:binance:ETHUSDT`

value(JSON)：

```json
{
  "max_position_size": 1.0,
  "max_long_position_size": 1.0,
  "max_short_position_size": 1.0,
  "max_drawdown_ratio": 0.2,
  "position_mode": "one_way",
  "allow_dual_side": false,
  "min_available_balance": 0.0,
  "max_symbol_exposure_ratio": 1.0,
  "max_account_notional": 1000000000.0,
  "max_margin_ratio": 1.0,
  "max_daily_loss": 1000000000.0,
  "max_consecutive_loss_count": 1000000000,
  "simulation_step_size": 0.1,
  "rule_priority_order": [
    "position_limit",
    "cooldown",
    "max_drawdown",
    "account_notional",
    "margin_ratio",
    "daily_loss",
    "consecutive_loss",
    "direction_conflict"
  ]
}
```

## 4) 环境变量

- `EXECUTION_STATE_PROVIDER_MODE=redis`
- `EXECUTION_REDIS_URL=redis://127.0.0.1:6379/0`
- `EXECUTION_POSITION_KEY_TEMPLATE=execution:position:{exchange}:{account_id}:{symbol}`
- `EXECUTION_ACCOUNT_KEY_TEMPLATE=execution:account:{exchange}:{account_id}`
- `EXECUTION_RISK_POLICY_KEY_TEMPLATE=execution:risk_policy:{exchange}:{symbol}`

幂等缓存（可选，mode=redis）：

- `EXECUTION_IDEMPOTENCY_ENABLED=true`
- `EXECUTION_IDEMPOTENCY_MODE=redis`
- `EXECUTION_IDEMPOTENCY_REDIS_URL=redis://127.0.0.1:6379/0`
- `EXECUTION_IDEMPOTENCY_KEY_TEMPLATE=execution:idempotency:{decision_id}`
- `EXECUTION_IDEMPOTENCY_TTL_S=3600`
- `EXECUTION_IDEMPOTENCY_LOCK_TTL_S=30`

对应 key 示例：

- `execution:idempotency:dec-001`
- `execution:idempotency:lock:dec-001`

状态机存储（可选，mode=redis）：

- `EXECUTION_STATE_MACHINE_ENABLED=true`
- `EXECUTION_STATE_MACHINE_MODE=redis`
- `EXECUTION_STATE_MACHINE_REDIS_URL=redis://127.0.0.1:6379/0`
- `EXECUTION_STATE_MACHINE_KEY_TEMPLATE=execution:state:{decision_id}`
- `EXECUTION_STATE_MACHINE_TTL_S=86400`

对应 key 示例：

- `execution:state:dec-001`

## 5) 说明

- 建议由下游账户/仓位同步任务持续刷新这些键。
- `account_id` 当前默认 `main`，后续可平滑扩展到多账户。
- 风控策略字段建议对齐 `services/execution_service/docs/risk_policy.schema.json`。
- 若键缺失，provider 会使用默认值回退，裁决逻辑仍可运行，但风险精度会下降。
