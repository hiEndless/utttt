# execution_service cURL 示例

更新时间：2026-03-10

## 1) stub 模式启动

```bash
EXECUTION_STATE_PROVIDER_MODE=stub \
EXECUTION_SERVICE_HOST=127.0.0.1 \
EXECUTION_SERVICE_PORT=9962 \
python -m execution_service.main
```

## 2) redis 模式启动

```bash
EXECUTION_STATE_PROVIDER_MODE=redis \
EXECUTION_REDIS_URL=redis://127.0.0.1:6379/0 \
EXECUTION_SERVICE_HOST=127.0.0.1 \
EXECUTION_SERVICE_PORT=9962 \
python -m execution_service.main
```

## 3) 健康检查

```bash
curl -s http://127.0.0.1:9962/internal/execution/healthz | jq
```

## 4) 版本检查

```bash
curl -s http://127.0.0.1:9962/internal/execution/version | jq
```

## 5) 执行裁决

```bash
curl -s -X POST http://127.0.0.1:9962/internal/execution/decide \
  -H 'Content-Type: application/json' \
  -d '{
    "decision_id":"dec-001",
    "exchange":"binance",
    "symbol":"ETHUSDT",
    "direction_intent":"long",
    "confidence":{"level":"medium","score":0.66},
    "cross_horizon_policy":{"suggested_policy":"follow_long_term"},
    "risk_hints":{"agent_action_hint":"add"}
  }' | jq
```

## 6) 调试状态（原始/脱敏）

```bash
curl -s http://127.0.0.1:9962/internal/execution/debug/state/binance/ETHUSDT | jq
curl -s 'http://127.0.0.1:9962/internal/execution/debug/state/binance/ETHUSDT?redact=true' | jq
```
