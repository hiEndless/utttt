# market_state_engine API

## 目标（冻结版）

对外提供稳定的市场状态接口，供：

- `agent_server_new`
- 调试 / 回放工具
- 未来研究与回测工具

消费状态层输出。

MSL 契约文件：

- `market_state_engine/docs/msl.schema.json`

## 接口列表

### `GET /internal/market-state/healthz`

用途：

- 服务健康检查

返回示例：

```json
{
  "ok": true,
  "service": "market_state_engine",
  "ts": 1741411200000,
  "ts_ms": 1741411200000
}
```

### `GET /internal/market-state/{exchange}/{symbol}`

用途：

- 返回指定交易所和交易对的状态层快照
- 正常场景输出状态推断结果
- 上游不可用场景输出 `status=data_unavailable` 的短路结果

## 正常响应（`status=ok`）

返回示例：

```json
{
  "exchange": "binance",
  "symbol": "BTCUSDT",
  "status": "ok",
  "msl": {},
  "msl_meta": {
    "schema_version": 2,
    "inference_version": "msl_generator_v1",
    "inference_profile": "default"
  },
  "state_features": {},
  "anomaly_flags": [],
  "msl_bundle": {
    "short_term": {},
    "mid_term": {},
    "long_term": {}
  },
  "msl_bundle_meta": {
    "short_term": {},
    "mid_term": {},
    "long_term": {}
  },
  "cross_horizon": {
    "alignment": "mixed",
    "conflicts": [],
    "suggested_policy": "reduce_risk",
    "policy_reason": "timeframe_mixed"
  },
  "raw_market_structure": {},
  "ts": 1741411200000,
  "ts_ms": 1741411200000
}
```

字段说明：

- `status`
  - `ok`：上游结构可用，已完成状态推断
- `msl`
  - 市场状态语言（供 agent 层直接消费）
  - 仅包含结构状态字段，不包含 `sentiment_state`
- `state_features`
  - 引擎聚合后的中间状态特征
  - 语义约定：`risk_flags` 为 `array[string]`；若需保留 map 明细使用 `risk_metrics`
  - 当接入 `selected_event_provider` 时，`state_features.evidence` 额外包含：
    - `selected_event_sources`（来源集合）
    - `selected_event_schema_versions`（trace.schema_version 集合）
- `msl_meta`
  - `schema_version`：MSL 契约版本（当前主分支为 `2`）
  - `inference_version`：推断生成器版本（如 `msl_generator_v1` / `msl_generator_v2`）
  - `inference_profile`：当前推断 profile（如 `default` / `fast_mode` / `risk_only`）
- `anomaly_flags`
  - 异常标签列表
- `msl_bundle`
  - 多周期状态快照：`short_term/mid_term/long_term`
- `msl_bundle_meta`
  - 多周期快照对应元信息（schema/inference/profile）
- `cross_horizon`
  - 周期关系摘要
  - `alignment`: `aligned|mixed|conflicting|unknown`
  - `conflicts`: 冲突明细数组
  - 冲突字段：`trend`、`phase`、`volatility_regime`、`liquidity_risk`
  - 冲突排序优先级：`trend > phase > volatility_regime > liquidity_risk`
  - `suggested_policy`: `follow_long_term|wait_confirmation|reduce_risk|no_action`
  - `policy_reason`: 策略建议命中原因
- `raw_market_structure`
  - 用于审计与调试的上游原始结构

## 上游不可用短路响应（`status=data_unavailable`）

当上游 `feature_service` 返回 `503 + detail.code=feature_data_unavailable` 时：

- `market_state_engine` 不再继续状态推断
- 返回 `HTTP 200`，并在响应体标记 `status=data_unavailable`

返回示例：

```json
{
  "exchange": "binance",
  "symbol": "ETHUSDT",
  "status": "data_unavailable",
  "reason_code": "feature_data_unavailable",
  "degraded_reasons": [
    "orderbook_provider_fallback",
    "open_interest_provider_fallback"
  ],
  "msl": {
    "version": 1,
    "timestamp": "2026-03-09T12:00:00Z",
    "symbol": "ETHUSDT",
    "anomalies": ["data_unavailable"],
    "summary": "上游 feature_service 关键结构数据不可用，状态推断已短路"
  },
  "state_features": {
    "status": "data_unavailable",
    "anomalies": {
      "flags": ["data_unavailable"]
    }
  },
  "anomaly_flags": ["data_unavailable"],
  "msl_meta": {
    "schema_version": 1,
    "inference_version": "short_circuit_unavailable",
    "inference_profile": "n/a"
  },
  "msl_bundle": {},
  "msl_bundle_meta": {},
  "cross_horizon": {
    "alignment": "unknown",
    "conflicts": [],
    "suggested_policy": "no_action",
    "policy_reason": "insufficient_evidence"
  },
  "raw_market_structure": {},
  "ts": 1741411200000,
  "ts_ms": 1741411200000
}
```

字段说明（短路场景）：

- `status = data_unavailable`
  - 下游应视为“数据层不可用”，不要当作“中性市场”
- `reason_code = feature_data_unavailable`
  - 上游统一错误码
- `degraded_reasons`
  - 上游降级原因，供重试/熔断/告警策略使用

## 上游依赖与契约

当前通过 HTTP 从 `feature_service` 读取：

- `GET /internal/feature-service/raw-structure/{exchange}/{symbol}`

上游契约识别：

- 成功场景读取 `data.raw_market_structure`
- 错误场景识别 `503 + detail.code=feature_data_unavailable`
- 不再兼容旧格式（例如顶层 `raw_market_structure` 直出）

## 约束

`market_state_engine` 不对外暴露 feature 计算细节，只暴露状态结果与审计所需原始结构。
