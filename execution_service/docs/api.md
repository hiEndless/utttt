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

建议标准拒绝码（首批冻结）：

- `position_limit_reached`
- `cooldown_active`
- `max_drawdown_exceeded`
- `direction_conflict_with_position`
