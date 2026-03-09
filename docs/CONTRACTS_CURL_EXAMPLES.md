# UTaker 联调 cURL 示例（新架构）

更新时间：2026-03-09

## 0. 环境变量

```bash
export FEATURE_BASE_URL="http://127.0.0.1:8001"
export STATE_BASE_URL="http://127.0.0.1:8002"
export EXCHANGE="binance"
export SYMBOL="ETHUSDT"
```

## 1. feature_service

### 1.1 健康检查

```bash
curl -sS "${FEATURE_BASE_URL}/internal/feature-service/healthz" | jq .
```

### 1.2 查询 raw structure

```bash
curl -sS "${FEATURE_BASE_URL}/internal/feature-service/raw-structure/${EXCHANGE}/${SYMBOL}" | jq .
```

期望重点字段：
- `meta.schema_version`
- `meta.degraded`
- `meta.degraded_reasons`
- `data.raw_market_structure`

### 1.3 查询 features

```bash
curl -sS "${FEATURE_BASE_URL}/internal/feature-service/features/${EXCHANGE}/${SYMBOL}" | jq .
```

期望重点字段：
- `data.indicators`
- `data.derived_metrics`
- `data.structure_snapshot`

### 1.4 检查 503 场景（关键数据不可用）

```bash
curl -sS -o /tmp/feature_err.json -w "%{http_code}\n" \
  "${FEATURE_BASE_URL}/internal/feature-service/raw-structure/${EXCHANGE}/${SYMBOL}"
cat /tmp/feature_err.json | jq .
```

若返回 `503`，应包含：
- `detail.code = "feature_data_unavailable"`
- `detail.degraded_reasons`（数组）

## 2. market_state_engine

### 2.1 健康检查

```bash
curl -sS "${STATE_BASE_URL}/internal/market-state/healthz" | jq .
```

### 2.2 查询 market state

```bash
curl -sS "${STATE_BASE_URL}/internal/market-state/${EXCHANGE}/${SYMBOL}" | jq .
```

期望重点字段：
- `status`（`ok` 或 `data_unavailable`）
- `msl`
- `state_features`
- `anomaly_flags`
- `raw_market_structure`

### 2.3 检查上游不可用短路语义

```bash
curl -sS "${STATE_BASE_URL}/internal/market-state/${EXCHANGE}/${SYMBOL}" | jq '{status, reason_code, degraded_reasons, anomaly_flags}'
```

当 feature 层不可用时，期望：
- HTTP 状态码仍为 `200`
- `status = "data_unavailable"`
- `reason_code = "feature_data_unavailable"`
- `degraded_reasons` 透传

## 3. 最小联调验收脚本（顺序执行）

```bash
set -euo pipefail

echo "[1/4] feature healthz"
curl -sS "${FEATURE_BASE_URL}/internal/feature-service/healthz" | jq .

echo "[2/4] feature raw-structure"
curl -sS "${FEATURE_BASE_URL}/internal/feature-service/raw-structure/${EXCHANGE}/${SYMBOL}" | jq .

echo "[3/4] state healthz"
curl -sS "${STATE_BASE_URL}/internal/market-state/healthz" | jq .

echo "[4/4] state snapshot"
curl -sS "${STATE_BASE_URL}/internal/market-state/${EXCHANGE}/${SYMBOL}" | jq .
```

## 4. 文档索引

- 架构总览：`ARCHITECTURE_NEW.md`
- 契约速查：`CONTRACTS_QUICK_REF.md`
- HTTPie 示例：`CONTRACTS_HTTPIE_EXAMPLES.md`
- 一键冒烟脚本：`scripts/integration_smoke_new_arch.sh`
- Feature API：`feature_service/docs/api.md`
- State API：`market_state_engine/docs/api.md`
