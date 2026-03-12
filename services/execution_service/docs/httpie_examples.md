# execution_service HTTPie 示例

更新时间：2026-03-10

## 1) 健康检查

```bash
http GET :9962/internal/execution/healthz
```

## 2) 版本检查

```bash
http GET :9962/internal/execution/version
```

## 3) 执行裁决

```bash
http POST :9962/internal/execution/decide \
  decision_id=dec-001 \
  exchange=binance \
  symbol=ETHUSDT \
  direction_intent=long \
  decision_confidence:='{"level":"medium","score":0.66}' \
  confidence:='{"level":"medium","score":0.66}' \
  cross_horizon_policy:='{"suggested_policy":"follow_long_term"}' \
  risk_hints:='{"agent_action_hint":"add"}'
```

## 4) 调试状态（原始/脱敏）

```bash
http GET :9962/internal/execution/debug/state/binance/ETHUSDT
http GET ':9962/internal/execution/debug/state/binance/ETHUSDT?redact=true'
```

## 5) 执行回执对账（reconcile）

```bash
http POST :9962/internal/execution/reconcile \
  order_id=mock-order-001 \
  decision_id=dec-001 \
  exchange=binance \
  symbol=ETHUSDT
```

## 6) 启动示例（stub / redis）

```bash
EXECUTION_STATE_PROVIDER_MODE=stub python -m services.execution_service.main

EXECUTION_STATE_PROVIDER_MODE=redis \
EXECUTION_REDIS_URL=redis://127.0.0.1:6379/0 \
python -m services.execution_service.main
```

## 7) 契约入口

- 项目级入口：`docs/CONTRACT_INDEX.md`
- API 说明：`services/execution_service/docs/api.md`

## 8) Schema 快速定位

- DecisionIntent：`services/execution_service/docs/decision_intent.schema.json`
- ExecutionResult：`services/execution_service/docs/execution_result.schema.json`
- DecisionState：`services/execution_service/docs/decision_state.schema.json`
