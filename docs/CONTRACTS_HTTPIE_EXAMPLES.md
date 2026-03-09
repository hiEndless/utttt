# UTaker 联调 HTTPie 示例（新架构）

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
http GET "${FEATURE_BASE_URL}/internal/feature-service/healthz"
```

### 1.2 查询 raw structure

```bash
http GET "${FEATURE_BASE_URL}/internal/feature-service/raw-structure/${EXCHANGE}/${SYMBOL}"
```

重点字段：
- `meta.schema_version`
- `meta.degraded`
- `meta.degraded_reasons`
- `data.raw_market_structure`

### 1.3 查询 features

```bash
http GET "${FEATURE_BASE_URL}/internal/feature-service/features/${EXCHANGE}/${SYMBOL}"
```

重点字段：
- `data.indicators`
- `data.derived_metrics`
- `data.structure_snapshot`

### 1.4 查看状态码（含 503 场景）

```bash
http --headers GET "${FEATURE_BASE_URL}/internal/feature-service/raw-structure/${EXCHANGE}/${SYMBOL}"
```

若关键数据不可用，预期：
- `HTTP/1.1 503`
- 响应体含 `detail.code=feature_data_unavailable`

## 2. market_state_engine

### 2.1 健康检查

```bash
http GET "${STATE_BASE_URL}/internal/market-state/healthz"
```

### 2.2 查询状态快照

```bash
http GET "${STATE_BASE_URL}/internal/market-state/${EXCHANGE}/${SYMBOL}"
```

重点字段：
- `status`（`ok` / `data_unavailable`）
- `msl`
- `state_features`
- `anomaly_flags`
- `raw_market_structure`

### 2.3 上游不可用短路检查

```bash
http GET "${STATE_BASE_URL}/internal/market-state/${EXCHANGE}/${SYMBOL}" | jq '{status, reason_code, degraded_reasons, anomaly_flags}'
```

预期（feature 不可用时）：
- HTTP 200
- `status=data_unavailable`
- `reason_code=feature_data_unavailable`

## 3. 文档索引

- 架构总览：`ARCHITECTURE_NEW.md`
- 契约速查：`CONTRACTS_QUICK_REF.md`
- cURL 示例：`CONTRACTS_CURL_EXAMPLES.md`
- 契约总索引：`CONTRACT_INDEX.md`

## 4. Execution Schema 快速定位

- DecisionIntent：`execution_service/docs/decision_intent.schema.json`
- ExecutionResult：`execution_service/docs/execution_result.schema.json`
- DecisionState：`execution_service/docs/decision_state.schema.json`
