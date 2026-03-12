# feature_service API

## 目标（冻结版）

对外提供稳定的内部接口，供下游服务按统一契约消费结构化数据：

- `market_state_engine`
- `event_center_new`
- 调试 / 回放工具

## 通用约定

### `GET /internal/feature-service/healthz`

用途：

- 服务健康检查

返回示例：

```json
{
  "ok": true,
  "service": "feature_service",
  "ts": 1741411200000,
  "ts_ms": 1741411200000
}
```

### `GET /internal/feature-service/version`

用途：

- 暴露 feature 层契约版本与响应 schema 版本，供跨服务守卫对齐

返回示例：

```json
{
  "service": "feature_service",
  "contract_version": "feature-contract-v1",
  "response_schema_version": "1.0",
  "ts": 1741411200000,
  "ts_ms": 1741411200000
}
```

### 标准响应结构（业务接口）

`/raw-structure` 与 `/features` 统一返回：

```json
{
  "meta": {
    "schema_version": "1.0",
    "generated_at_ms": 1741411200000,
    "degraded": false,
    "degraded_reasons": []
  },
  "data": {}
}
```

字段说明：

- `meta.schema_version`
  - 当前固定为 `"1.0"`，用于下游版本分流
- `meta.generated_at_ms`
  - 响应生成时间戳（毫秒）
- `meta.degraded`
  - 是否触发降级路径
- `meta.degraded_reasons`
  - 降级原因列表（如 `orderbook_provider_fallback`）

### `GET /internal/feature-service/raw-structure/{exchange}/{symbol}`

用途：

- 返回标准化后的 `raw_market_structure`
- 给 `market_state_engine` 作为上游输入

返回示例：

```json
{
  "meta": {
    "schema_version": "1.0",
    "generated_at_ms": 1741411200000,
    "degraded": true,
    "degraded_reasons": ["horizons_provider_fallback"]
  },
  "data": {
    "exchange": "binance",
    "symbol": "BTCUSDT",
    "raw_market_structure": {
      "symbol": "BTCUSDT",
      "candidate_horizons": ["short_term", "mid_term", "long_term"],
      "pre_decision_structure": {},
      "horizons": {},
      "orderbook": {},
      "open_interest": {},
      "behavioral": {}
    }
  }
}
```

### `GET /internal/feature-service/features/{exchange}/{symbol}`

用途：

- 返回完整 feature snapshot
- 给 `event_center_new` / `market_state_engine` / 调试工具消费

返回示例：

```json
{
  "meta": {
    "schema_version": "1.0",
    "generated_at_ms": 1741411200000,
    "degraded": false,
    "degraded_reasons": []
  },
  "data": {
    "exchange": "binance",
    "symbol": "BTCUSDT",
    "indicators": {},
    "derived_metrics": {
      "candidate_horizons": ["short_term", "mid_term", "long_term"],
      "indicator_metrics": {},
      "horizon_metrics": {},
      "orderbook_metrics": {},
      "open_interest_metrics": {},
      "behavior_metrics": {},
      "pre_decision_metrics": {}
    },
    "structure_snapshot": {
      "pre_decision_structure": {},
      "horizons": {}
    },
    "alternative_sources": {
      "news": {"source_type": "news", "available": false, "provider_state": "noop", "data_source": "feature_service.news", "inference_source": "feature_service.normalizer", "as_of_ms": null, "features": {}},
      "social": {"source_type": "social", "available": false, "provider_state": "noop", "data_source": "feature_service.social", "inference_source": "feature_service.normalizer", "as_of_ms": null, "features": {}},
      "onchain": {"source_type": "onchain", "available": false, "provider_state": "noop", "data_source": "feature_service.onchain", "inference_source": "feature_service.normalizer", "as_of_ms": null, "features": {}}
    }
  }
}
```

说明：

- `data.indicators`：多周期基础指标原始输出
- `data.derived_metrics`：面向下游复用的摘要特征
- `data.structure_snapshot`：保留较完整的结构快照，供状态层与调试使用
- `data.alternative_sources`：未来数据源统一包（news/social/onchain），字段稳定但当前默认 `noop`。

## 错误响应

### `503 feature_data_unavailable`

当关键结构数据（`orderbook/open_interest/horizons/behavioral`）同时不可用时返回：

```json
{
  "detail": {
    "code": "feature_data_unavailable",
    "message": "关键结构数据不可用，请稍后重试",
    "exchange": "binance",
    "symbol": "ETHUSDT",
    "degraded_reasons": [
      "orderbook_provider_fallback",
      "open_interest_provider_fallback"
    ]
  }
}
```

下游建议：

- 将该错误视为“数据层不可用”而非“业务判定为中性”
- 根据 `degraded_reasons` 做重试、熔断或降级策略

## 下游对接要求

`market_state_engine` 与其他下游必须按以下字段读取：

- `data.raw_market_structure`

不再支持旧格式解析路径（如顶层 `raw_market_structure` 直出）。
