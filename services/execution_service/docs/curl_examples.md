# execution_service cURL 示例

更新时间：2026-03-10

## 1) redis 模式启动

```bash
EXECUTION_STATE_PROVIDER_MODE=redis \
EXECUTION_REDIS_URL=redis://127.0.0.1:6379/0 \
EXECUTION_SERVICE_HOST=127.0.0.1 \
EXECUTION_SERVICE_PORT=9962 \
python -m services.execution_service.main
```

## 2) 健康检查

```bash
curl -s http://127.0.0.1:9962/internal/execution/healthz | jq
```

## 3) 版本检查

```bash
curl -s http://127.0.0.1:9962/internal/execution/version | jq
```

## 4) 执行裁决

```bash
curl -s -X POST http://127.0.0.1:9962/internal/execution/decide \
  -H 'Content-Type: application/json' \
  -d '{
    "decision_id":"dec-001",
    "exchange":"binance",
    "symbol":"ETHUSDT",
    "direction_intent":"long",
    "decision_confidence":{"level":"medium","score":0.66},
    "confidence":{"level":"medium","score":0.66},
    "cross_horizon_policy":{"suggested_policy":"follow_long_term"},
    "risk_hints":{"agent_action_hint":"add"}
  }' | jq
```

## 5) 调试状态（原始/脱敏）

```bash
curl -s http://127.0.0.1:9962/internal/execution/debug/state/binance/ETHUSDT | jq
curl -s 'http://127.0.0.1:9962/internal/execution/debug/state/binance/ETHUSDT?redact=true' | jq
```

## 6) 执行回执对账（reconcile）

```bash
curl -s -X POST http://127.0.0.1:9962/internal/execution/reconcile \
  -H 'Content-Type: application/json' \
  -d '{
    "order_id":"mock-order-001",
    "decision_id":"dec-001",
    "exchange":"binance",
    "symbol":"ETHUSDT"
  }' | jq
```

## 7) 契约入口

- 项目级入口：`docs/CONTRACT_INDEX.md`
- API 说明：`services/execution_service/docs/api.md`

## 8) Schema 快速定位

- DecisionIntent：`services/execution_service/docs/decision_intent.schema.json`
- ExecutionResult：`services/execution_service/docs/execution_result.schema.json`
- DecisionState：`services/execution_service/docs/decision_state.schema.json`
