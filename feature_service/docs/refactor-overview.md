# feature_service 重构完成态说明

## 1. 重构完成后的主要功能

### 1.1 结构化特征生产（Feature Layer）

`feature_service` 已完成从“调用旧聚合器”到“本层统一组装”的收敛，当前核心能力是：

- 并发拉取结构输入：
  - `orderbook`
  - `open_interest`
  - `horizons`
  - `behavioral`
  - `indicators`
- 统一构建：
  - `raw_market_structure`
  - `features`（`indicators + derived_metrics + structure_snapshot`）
- 对输出做统一标准化：
  - `exchange/symbol` 规范化
  - `candidate_horizons` 合法化与顺序稳定
  - 空值兜底与字段补齐

### 1.2 Provider 注入与降级容错

当前运行路径是独立 provider 注入模式（非 compat 过渡模式）：

- 主路径：`migrated_structure_providers`
- 降级路径：`fallback_structure_providers` -> `static/noop`
- 指标异常处理：`FallbackIndicatorsProvider` 或 `UnavailableIndicatorsProvider`

这让服务具备：

- 主链路异常时不中断服务
- 降级信息可观测、可透传

### 1.3 请求级降级可观测性

通过 `degradation_state` 在单次请求内收集 `degraded_reasons`，并透传到响应 `meta`：

- `meta.degraded`
- `meta.degraded_reasons`

下游可据此区分：

- 正常数据
- 降级数据（可用但质量下降）
- 硬失败数据（不可用）

### 1.4 硬失败保护（避免“空结构误判”）

当关键结构同时为空（`orderbook/open_interest/horizons/behavioral`）时，服务不返回“看似正常的空结构”，而是：

- 抛出 `FeatureDataUnavailableError`
- 路由层映射为 `HTTP 503`
- 错误码：`feature_data_unavailable`

此策略可以避免下游把“数据缺失”误当成“中性行情”。

## 2. 对下游输出的内容（当前契约）

## 2.1 通用响应外壳（`meta + data`）

业务接口统一返回：

- `meta.schema_version`
- `meta.generated_at_ms`
- `meta.degraded`
- `meta.degraded_reasons`
- `data`（业务负载）

## 2.2 `GET /internal/feature-service/raw-structure/{exchange}/{symbol}`

下游主要拿到：

- `data.exchange`
- `data.symbol`
- `data.raw_market_structure`

其中 `raw_market_structure` 当前包含：

- `symbol`
- `candidate_horizons`
- `pre_decision_structure`
- `horizons`
- `orderbook`
- `open_interest`
- `behavioral`

适用下游：

- `market_state_engine`（结构态输入）
- 调试/回放工具（结构追踪）

## 2.3 `GET /internal/feature-service/features/{exchange}/{symbol}`

下游主要拿到：

- `data.exchange`
- `data.symbol`
- `data.indicators`
- `data.derived_metrics`
- `data.structure_snapshot`

其中 `derived_metrics` 当前稳定键包括：

- `candidate_horizons`
- `indicator_metrics`
- `horizon_metrics`
- `orderbook_metrics`
- `open_interest_metrics`
- `behavior_metrics`
- `pre_decision_metrics`

适用下游：

- `event_center_new`（事件候选特征输入）
- `market_state_engine`（状态推断辅助特征）

## 2.4 错误输出（关键结构不可用）

当关键结构不可用时：

- HTTP 状态：`503`
- `detail.code = "feature_data_unavailable"`
- `detail.exchange`
- `detail.symbol`
- `detail.degraded_reasons`

下游建议：

- 将其视为“数据不可用”而不是“策略中性”
- 根据 `degraded_reasons` 执行重试/熔断/降级策略

## 3. 下游消费建议（重构完成态）

建议下游统一按以下优先级消费：

1. 只依赖 `meta + data` 新契约
2. 先看 `meta.degraded`，再决定是否启用风险保护分支
3. 对 `503 feature_data_unavailable` 走数据层异常处理，不走业务正常分支

## 4. 后续演进建议

1. 将 `raw_market_structure` 与 `derived_metrics` 从 `Dict[str, Any]` 逐步收敛为强类型契约。
2. 对 `degraded_reasons` 增加分类（数据缺失、超时、解析失败）以支持下游精细化恢复策略。
3. 增加端到端契约回归（feature_service -> market_state_engine -> event_center_new）防止字段漂移。
