# market_state_engine 数据流水线与字段契约（实现对齐版）

本文档面向 `/services/market_state_engine` 当前代码实现，按“真实执行顺序”梳理数据流水线各环节的输入输出、字段枚举与字段含义说明；并明确与上游 `feature_service`、可选上游 `event_center_new`（selected events）之间的契约边界。

主要依据：
- 路由入口：[routes.py](services/market_state_engine/src/routes.py)
- 应用装配（Provider/Service/Router）：[app.py](services/market_state_engine/src/app.py)
- Service 聚合与降级策略：[service.py](services/market_state_engine/src/service.py)
- 引擎特征聚合与多周期冲突：[engine.py](services/market_state_engine/src/engine.py)
- MSL 数据结构与枚举：[contracts.py](services/market_state_engine/src/contracts.py)
- MSL JSON Schema（强约束枚举）：[msl.schema.json](services/market_state_engine/docs/msl.schema.json)
- State inference 插件与 meta：[state_inference/engine.py](services/market_state_engine/src/state_inference/engine.py)
- 与上游边界说明：[boundaries.md](services/market_state_engine/docs/boundaries.md)

时间语义口径（canonical）：`docs/contracts/SEMANTIC_GLOSSARY.md`
- API 响应元字段：`ts/ts_ms`（兼容保留）
- 事件语义字段（来自 selected_event）：`event_ts_ms`（发生时间）/`processed_ts_ms`（处理时间）
- `ts_ms` 在 selected_event 语义中仅作为兼容别名

---

## 0. 总览：端到端“真实执行顺序”

一次 `GET /internal/market-state/{exchange}/{symbol}` 的完整链路：

1. HTTP 路由校验参数并补充 `ts/ts_ms`（响应时间戳）
2. Service 拉取上游 `raw_market_structure`（HTTP）
3. 输入守卫：剔除外部事件域字段（news/social/onchain/...），打标记
4. （可选）从 Redis Stream 拉取 `event_center_new` 的 `SelectedEvent`（ec:selected）
5. 引擎聚合 features（horizons/orderbook/OI/derived）
6. anomaly 检测（输出 `features.anomalies`）
7. evidence 抽取（输出 `features.evidence`）
8. state_inference 插件推断 + MSL 生成（输出 `msl` 与 `msl_meta`）
9. （可选）多周期推断（输出 `msl_bundle/msl_bundle_meta/cross_horizon`）
10. Service 组装最终响应（`status=ok` 或短路 `status=data_unavailable`）

---

## 1. 对外 API（HTTP）

### 1.1 Health Check

接口：`GET /internal/market-state/healthz`  
返回字段：

| 字段 | 类型 | 必填 | 含义 |
|---|---:|:---:|---|
| ok | bool | Y | 固定 true |
| service | string | Y | 固定 `"market_state_engine"` |
| ts | int | Y | 毫秒时间戳（当前时间） |
| ts_ms | int | Y | 同 ts（兼容字段） |

实现：[routes.py](services/market_state_engine/src/routes.py#L14-L18)

### 1.2 状态快照

接口：`GET /internal/market-state/{exchange}/{symbol}`  
输入：

| 参数 | 类型 | 必填 | 规范 |
|---|---|:---:|---|
| exchange | path string | Y | `strip()` 后不能为空（原样透传给上游 provider） |
| symbol | path string | Y | `strip().upper()` 后不能为空（如 `ETHUSDT`） |

实现：[routes.py](services/market_state_engine/src/routes.py#L19-L38)

---

## 2. 上游输入：feature_service raw structure（HTTP）

### 2.1 Provider 与接口

Provider：`HttpRawStructureProvider`  
拉取接口（上游）：`GET {RAW_STRUCTURE_PROVIDER_URL}/internal/feature-service/raw-structure/{exchange}/{symbol}`  
实现：[raw_structure_http.py](services/market_state_engine/src/adapters/raw_structure_http.py#L11-L42)

### 2.2 成功响应契约（新契约）

Provider 只接受以下形态（只取 `data.raw_market_structure`）：

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
    "symbol": "ETHUSDT",
    "raw_market_structure": { "...": "..." }
  }
}
```

测试对齐：[test_raw_structure_http_provider_contract.py](verification/validators/market_state_engine/test_raw_structure_http_provider_contract.py#L10-L38)

### 2.3 上游不可用的业务错误映射（短路触发）

当上游返回：
- HTTP 503
- 且响应 JSON 满足 `detail.code == "feature_data_unavailable"`

则 Provider 抛出 `FeatureDataUnavailableFromUpstreamError(exchange, symbol, degraded_reasons)`，交由 Service 做“短路返回（HTTP 200 + status=data_unavailable）”。

对应测试：[test_raw_structure_http_provider_contract.py](verification/validators/market_state_engine/test_raw_structure_http_provider_contract.py#L40-L62)

### 2.4 raw_market_structure 的“必需子集”

`market_state_engine` 不尝试定义/冻结上游 `raw_market_structure` 的完整 schema；但引擎聚合阶段会**读取并依赖**如下字段路径（缺失会回落为空 dict/0 值）：

| 字段路径 | 类型 | 用途 |
|---|---|---|
| horizons.fused.horizons.short_term / mid_term / long_term | object | 多周期背景信息（趋势/结构/风险/波动等） |
| horizons.fused.horizons.{hz}.market_background.trend_memory | object | 证据抽取与 regime 推断（如 `price_direction/price_strength`） |
| horizons.fused.horizons.{hz}.market_background.trend_context | any | 参与 regime 推断（通常是带 label 的对象） |
| horizons.fused.horizons.{hz}.market_background.structure_state | any | 透传给 `state_features`（审计/调试） |
| horizons.fused.horizons.{hz}.market_background.risk_level | any | 透传给 `state_features`（审计/调试） |
| horizons.fused.horizons.{hz}.market_background.volatility_state | any | 参与波动推断与 evidence |
| horizons.fused.horizons.{hz}.participant_background | object | 参与拥挤度/稳定性推断与 evidence |
| pre_decision_structure.short_term.micro_liquidity.meta.stability | string | orderbook 稳定性（稳定/脆弱等，原样透传） |
| pre_decision_structure.short_term.micro_liquidity.risk_flags | object | orderbook 风险明细（map 语义保留） |
| pre_decision_structure.short_term.structural_risks | object | 派生/冗余信息透传与 `liquidity_vacuum` 判断 |
| pre_decision_structure.mid_term.participant_positioning.oi_delta.delta_oi_pct | number | OI 变化百分比（anomaly 检测） |
| pre_decision_structure.mid_term.participant_positioning.oi_dynamics | object | OI 趋势/速度/加速度（推断与 evidence） |
| pre_decision_structure.mid_term.participant_positioning.risk_flags | object\|array | OI 风险标记（归一化成 list） |
| pre_decision_structure.long_term.structural_context | object | `leverage_extreme/crowding_percentile.zone` 等 anomaly 检测 |

聚合实现参考：[engine.py](services/market_state_engine/src/engine.py#L87-L188)

---

## 3. 输入守卫：剔除外部事件域字段（boundary guard）

Service 在拿到 `raw_market_structure` 后会做清洗：删除输入中混入的外部事件域字段（不参与状态推断）。

### 3.1 被剔除的 key 集合（大小写不敏感）

固定集合：

- news
- social
- onchain
- sentiment
- external_events
- active_events
- event_stream

实现：[service.py](services/market_state_engine/src/service.py#L15-L43)

### 3.2 清洗后的影响（输出标记）

若有字段被剔除：

- `anomaly_flags` 增加：`external_event_input_ignored`
- `msl.anomalies` 增加：`external_event_input_ignored`
- `state_features.anomalies.flags` 增加：`external_event_input_ignored`
- `state_features.evidence.ignored_external_input_keys` 增加：被剔除 key 列表

实现：[service.py](services/market_state_engine/src/service.py#L297-L315)

---

## 4. 可选输入：event_center_new SelectedEvent（Redis Stream）

### 4.1 接入方式

当环境变量 `MSE_SELECTED_EVENT_PROVIDER_MODE=redis` 时启用 `RedisSelectedEventProvider`，从 stream（默认 `ec:selected`）逆序扫描最新事件并按 asset 精确匹配。

装配实现：[app.py](services/market_state_engine/src/app.py#L23-L37)  
读取实现：[selected_events_redis.py](services/market_state_engine/src/adapters/selected_events_redis.py#L34-L80)

### 4.2 匹配规则（asset 精确匹配）

`SelectedEvent.asset` 支持两种形态：

- `exchange:symbol`：例如 `binance:ETHUSDT`（会同时校验 exchange 与 symbol）
- `symbol`：例如 `ETHUSDT`（必须与 symbol 完全相等，禁止子串匹配）

实现：[selected_events_redis.py](services/market_state_engine/src/adapters/selected_events_redis.py#L68-L80)

### 4.3 consumer 侧最小必需字段（market_state_engine 读取的子集）

Service 不要求 SelectedEvent 具备完整契约，但会从每条事件中读取以下字段做 evidence 汇总（缺失会被忽略或计为 unversioned）：

| 字段路径 | 类型 | 用途 |
|---|---|---|
| asset | string | 匹配路由（见 4.2） |
| selected_type | string | 汇总到 `selected_event_types` |
| priority | string | 汇总到 `selected_event_priorities` |
| direction_hint | string | 汇总到 `selected_event_directions` |
| event_ts_ms / ts_ms | int | 事件时间（优先 event_ts_ms，缺失回退 ts_ms） |
| processed_ts_ms / ts_ms | int | 处理时间（优先 processed_ts_ms，缺失回退 ts_ms） |
| source / source.name | string\|object | 汇总到 `selected_event_sources` |
| trace.schema_version | string | 汇总到 `selected_event_schema_versions`；缺失会计入 `selected_events_unversioned_count` |

其中枚举约束（来自上游 `event_center_new` 的 SelectedEvent 契约）：

| 字段 | 枚举 |
|---|---|
| direction_hint | bullish / bearish / neutral / mixed |
| priority | low / medium / high |

汇总逻辑：[service.py](services/market_state_engine/src/service.py#L180-L227)

SelectedEvent 的完整语义契约参考（上游实现对齐版文档）：
- [event_center_new_data_contracts.md](docs/contracts/pipelines/event_center_new_data_contracts.md#L368-L414)

### 4.4 selected events 融合到输出的规则

- 若读到 `selected_events`（非空）：
  - `anomaly_flags` 增加：`selected_event_context_attached`
  - `state_features.evidence` 注入 selected events 汇总字段 + `selected_events_preview`（最多 3 条）
  - 若存在 `trace.schema_version` 缺失：
    - `anomaly_flags` 增加：`selected_events_unversioned`
    - 会输出告警日志（不改变响应结构）
- 若读取失败：
  - `anomaly_flags` 增加：`selected_events_unavailable`
  - `state_features.evidence.selected_events_unavailable = true`

实现：[service.py](services/market_state_engine/src/service.py#L272-L296)

---

## 5. 引擎聚合阶段：raw_market_structure -> MarketStateFeatures

引擎聚合输出 `MarketStateFeatures`，随后用于 anomaly 检测、evidence 抽取与状态推断。

数据结构：[engine.py](services/market_state_engine/src/engine.py#L44-L71)

### 5.1 MarketStateFeatures 顶层字段

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| exchange | string | Y | 交易所（来自 API path） |
| symbol | string | Y | 交易对（来自 API path，已 upper） |
| ts | int | Y | features 生成时间（ms） |
| horizons | object | Y | 多周期结构背景（见 5.2） |
| orderbook | object | Y | 订单簿/微观流动性摘要（见 5.3） |
| open_interest | object | Y | OI 摘要（见 5.4） |
| anomalies | object | Y | 异常检测输出（见 6） |
| evidence | object | Y | 证据层摘要（见 7） |
| derived | object | Y | 派生透传字段（见 5.5） |

### 5.2 horizons（多周期背景）

`horizons` 固定包含：`short_term/mid_term/long_term` 三个对象，每个对象字段：

| 字段路径 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| horizons.{hz}.market_background | object | Y | 周期背景摘要 |
| horizons.{hz}.participant_background | object | Y | 参与者背景（透传上游对象） |
| horizons.{hz}.confidence | number | Y | 上游 horizon confidence（缺失为 0.0） |
| horizons.{hz}.horizon_confidence | number | Y | 同 confidence（兼容字段） |

其中 `market_background` 字段：

| 字段 | 类型 | 含义 |
|---|---|---|
| trend_memory | object | 趋势记忆（通常包含 `price_direction/price_strength` 等） |
| trend_context | any | 趋势语境（通常带 label） |
| structure_state | any | 结构状态（透传） |
| risk_level | any | 风险等级（透传） |
| volatility_state | any | 波动状态（透传；也会参与 volatility 推断） |

实现：[engine.py](services/market_state_engine/src/engine.py#L117-L154)

### 5.3 orderbook（微观流动性）

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| stability | string | Y | 上游 meta.stability（原样字符串） |
| liquidity_vacuum | bool | Y | 流动性真空标记（短线结构风险或 risk_flags 指示） |
| risk_flags | array[string] | Y | 风险标签列表（从 map/array 归一化） |
| risk_metrics | object | Y | 风险明细 map（原样保留，避免信息丢失） |

实现：[engine.py](services/market_state_engine/src/engine.py#L156-L163)

### 5.4 open_interest（OI）

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| delta_oi_pct | number | Y | OI 变化百分比（缺失为 0.0） |
| oi_trend | string | Y | 趋势（原样字符串） |
| oi_velocity | string | Y | 速度（原样字符串） |
| oi_acceleration | string | Y | 加速度（原样字符串） |
| risk_flags | array[string] | Y | 风险标签列表（map/array 归一化） |

实现：[engine.py](services/market_state_engine/src/engine.py#L164-L170)

### 5.5 derived（派生透传）

用于调试/审计，不参与下游契约冻结，但会作为响应字段输出。

| 字段 | 类型 | 含义 |
|---|---|---|
| pre_decision_short_term_structural_risks | object | 透传 `pre_decision_structure.short_term.structural_risks` |
| pre_decision_mid_term_structural_risks | object | 透传 `pre_decision_structure.mid_term.structural_risks` |
| pre_decision_long_term_structural_context | object | 透传 `pre_decision_structure.long_term.structural_context` |

实现：[engine.py](services/market_state_engine/src/engine.py#L172-L176)

### 5.6 （可选）FeatureStore 缓存层

`MarketStateEngine` 支持注入 `FeatureStore` 用于缓存 `MarketStateFeatures`（默认不启用）。若命中缓存则跳过 `aggregate_features`，直接复用缓存 features 进入 anomaly/evidence/inference。

| 点位 | 说明 |
|---|---|
| 接口 | `FeatureStore.get(exchange, symbol) -> MarketStateFeatures|None`；`put(features)` |
| 默认实现 | `InMemoryFeatureStore(ttl_ms=15000, max_items=256)`（开发/单机用途） |
| 命中逻辑 | 若 `feature_store.get(...)` 返回非空，则使用该 features；否则新聚合后 put |

参考实现：[engine.py](services/market_state_engine/src/engine.py#L399-L421) 与 [in_memory_feature_store.py](services/market_state_engine/src/adapters/in_memory_feature_store.py)

---

## 6. anomaly 检测：features -> features.anomalies

输出结构：

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| anomalies.flags | array[string] | Y | 异常标签集合（去重并排序） |
| anomalies.oi_spike | object | N | 当触发 `oi_spike` 时附带明细 `{delta_oi_pct}` |

实现：[engine.py](services/market_state_engine/src/engine.py#L190-L221)

### 6.1 已实现的异常标签与触发条件（强实现约束）

| flag | 触发条件（当前实现） | 说明 |
|---|---|---|
| orderbook_liquidity_vacuum | `orderbook.liquidity_vacuum == true` | 订单簿流动性真空 |
| oi_spike | `abs(open_interest.delta_oi_pct) >= 0.03` | OI 变化过大 |
| liquidation_cluster | `open_interest.risk_flags` 包含 `possible_liquidation_or_unwind` 或 `fragile_leverage_build` | 疑似清算簇/脆弱杠杆 |
| leverage_extreme | `derived.pre_decision_long_term_structural_context.leverage_extreme == true` | 杠杆极端 |
| crowding_extreme | `derived...crowding_percentile.zone in {elevated, extreme}` | 拥挤度极端 |

---

## 7. evidence 抽取：features -> features.evidence

evidence 层为“少字段、稳定摘要”，既用于 LLM 可解释摘要，也用于调试。

实现：[engine.py](services/market_state_engine/src/engine.py#L223-L248)

### 7.1 字段表（引擎输出）

| 字段 | 类型 | 含义 |
|---|---|---|
| price_direction_mid | string | mid_term 趋势方向（来自 `trend_memory.price_direction`） |
| price_strength_mid | string | mid_term 趋势强度（来自 `trend_memory.price_strength`） |
| volatility_state_mid | string | mid_term 波动状态（来自 `market_background.volatility_state`） |
| crowding_mid | string | mid_term 拥挤度（来自 `participant_background.crowding`） |
| participant_stability_mid | string | mid_term 参与者稳定性（来自 `participant_background.stability`） |
| liquidity_vacuum | bool | 是否流动性真空（来自 `orderbook.liquidity_vacuum`） |
| orderbook_stability | string | orderbook 稳定性（来自 `orderbook.stability`） |
| oi_trend | string | OI 趋势（来自 `open_interest.oi_trend`） |
| oi_velocity | string | OI 速度（来自 `open_interest.oi_velocity`） |
| oi_acceleration | string | OI 加速度（来自 `open_interest.oi_acceleration`） |
| delta_oi_pct | number | OI 变化百分比（来自 `open_interest.delta_oi_pct`） |
| anomaly_flags | array[string] | anomalies.flags 的拷贝（便于下游直接读） |

### 7.2 Service 注入的 selected events evidence（可选）

当 selected events 非空时，Service 会在 `state_features.evidence` 上叠加以下字段：

| 字段 | 类型 | 含义 |
|---|---|---|
| selected_events_count | int | 匹配到的事件数量 |
| selected_event_types | array[string] | `selected_type` 的集合 |
| selected_event_priorities | array[string] | `priority` 的集合 |
| selected_event_directions | array[string] | `direction_hint` 的集合 |
| selected_event_assets | array[string] | `asset` 的集合 |
| selected_event_sources | array[string] | `source.name`（或 source 字符串）集合 |
| selected_event_schema_versions | array[string] | `trace.schema_version` 集合 |
| selected_events_unversioned_count | int | `trace.schema_version` 缺失的事件数量 |
| selected_events_preview | array[object] | 前 3 条原始事件 payload（审计/调试） |

实现：[service.py](services/market_state_engine/src/service.py#L180-L227)

---

## 8. 状态推断：features -> MSL（state_inference）

### 8.1 插件流水线与 profile

默认插件顺序（稳定依赖拓扑）：

- regime_inference
- positioning_inference
- volatility_inference
- liquidity_inference
- risk_inference
- structure_inference

实现：[state_inference/engine.py](services/market_state_engine/src/state_inference/engine.py#L89-L99)

预设 profile：

| profile | 插件集合 |
|---|---|
| default | 全量（6 个插件） |
| fast_mode | 去掉 structure_inference |
| risk_only | 仅 regime_inference + risk_inference |

实现：[state_inference/engine.py](services/market_state_engine/src/state_inference/engine.py#L23-L46)

### 8.2 msl_meta（推断元信息）

每次推断会输出 meta（Service 将其放入 `msl_meta`，多周期推断放入 `msl_bundle_meta`）：

| 字段 | 类型 | 含义 |
|---|---|---|
| schema_version | int | 等于 `msl.version` |
| inference_version | string | 实际使用的生成器（`msl_generator_v1/v2`） |
| inference_version_requested | string | 请求的生成器版本（配置项） |
| inference_profile | string | profile 名称（default/fast_mode/risk_only） |
| supported_inference_versions | array[string] | 当前支持的生成器版本列表 |

实现：[state_inference/engine.py](services/market_state_engine/src/state_inference/engine.py#L147-L172)

### 8.3 （中间层）state_inference 关键 state 字段（非对外冻结）

以下字段是插件之间传递/融合用的中间 state（实现内已较稳定，但不建议当作对外 API 契约冻结）。这里列出主要字段、允许值与它们如何映射到最终 MSL：

| state key | 允许值（当前实现） | 来源 | 最终映射 |
|---|---|---|---|
| direction_bias | bullish / bearish / neutral / unknown | [factors/regime.py](services/market_state_engine/src/factors/regime.py#L6-L13) | 参与推导 `market_regime.trend` 等 |
| trend_strength | strong / medium / weak / unknown | [factors/regime.py](services/market_state_engine/src/factors/regime.py#L16-L19) | 参与推导 `market_regime.strength` |
| horizon_alignment | aligned / mixed / conflict / unknown | [factors/regime.py](services/market_state_engine/src/factors/regime.py#L22-L37) | 推导 `market_regime.timeframe_alignment`（conflict -> conflicting） |
| regime | trend / range / transition / breakdown / unknown | [factors/regime.py](services/market_state_engine/src/factors/regime.py#L39-L50) | 推导结构与 phase |
| crowding_out | high / normal / low / insufficient_evidence / unknown | [positioning_inference.py](services/market_state_engine/src/state_inference/positioning_inference.py#L15-L36) | 推导 `positioning_state.crowding` 与风险 |
| participant_behavior | adding_leverage / reducing_leverage / rotation / unclear / unknown | [factors/positioning.py](services/market_state_engine/src/factors/positioning.py#L6-L11) | 参与推导 phase/expansion_risk |
| oi_trend | expanding / contracting / flat / unknown | [factors/positioning.py](services/market_state_engine/src/factors/positioning.py#L14-L17) | `positioning_state.oi_trend` |
| volatility_state | low / normal / high / unknown | [factors/volatility.py](services/market_state_engine/src/factors/volatility.py#L6-L17) | `volatility_state.volatility_regime` |
| expansion_risk | expanding / compressing / unknown | [factors/volatility.py](services/market_state_engine/src/factors/volatility.py#L20-L27) | `volatility_state.expansion_risk` |
| volatility_direction | upside / downside / neutral / unknown | [factors/volatility.py](services/market_state_engine/src/factors/volatility.py#L30-L37) | `volatility_state.volatility_direction` |
| dominant_pressure | buyers / sellers / balanced / unknown | [factors/liquidity.py](services/market_state_engine/src/factors/liquidity.py#L18-L25) | `liquidity_state.dominant_pressure` |
| orderbook_bias | bid_heavy / ask_heavy / neutral / unknown | [factors/liquidity.py](services/market_state_engine/src/factors/liquidity.py#L28-L33) | `liquidity_state.orderbook_bias` |
| liquidity_risk | short_squeeze / long_squeeze / neutral / unknown | [factors/liquidity.py](services/market_state_engine/src/factors/liquidity.py#L36-L43) | `liquidity_state.liquidity_risk` |
| liquidation_proximity | above / below / both / none / unknown | [factors/liquidity.py](services/market_state_engine/src/factors/liquidity.py#L46-L49) | `liquidity_state.liquidation_proximity` |
| market_fragility | low / medium / high / unknown | [factors/risk.py](services/market_state_engine/src/factors/risk.py#L23-L45) | 参与推导 `market_regime.strength` 与风险 |
| market_phase | expansion / distribution / contraction / accumulation / unknown | [factors/regime.py](services/market_state_engine/src/factors/regime.py#L52-L66) | 推导 `market_regime.phase` |
| range_state | breakout / range / breakdown / unknown | [factors/structure.py](services/market_state_engine/src/factors/structure.py#L6-L13) | `market_structure_state.range_state` |
| trend_structure | hh_hl / lh_ll / mixed / unknown | [factors/structure.py](services/market_state_engine/src/factors/structure.py#L16-L24) | `market_structure_state.trend_structure` |
| cascade_risk | high / medium / low / unknown | [factors/risk.py](services/market_state_engine/src/factors/risk.py#L48-L51) | `market_risk_state.cascade_risk` |
| squeeze_probability | high / medium / low / unknown | [factors/risk.py](services/market_state_engine/src/factors/risk.py#L54-L77) | `market_risk_state.squeeze_probability` |
| reversal_risk | high / medium / low / unknown | [factors/risk.py](services/market_state_engine/src/factors/risk.py#L79-L97) | `market_risk_state.reversal_risk` |

---

## 9. MSL 输出（对下游冻结的稳定语义层）

### 9.1 输出形态

对外（API）输出的 MSL 来自 `MarketStateMSL.to_llm_dict()`，字段集合固定：

- version（int）
- timestamp（ISO8601 string）
- symbol（string）
- market_regime（object）
- liquidity_state（object）
- positioning_state（object）
- volatility_state（object）
- market_risk_state（object）
- market_structure_state（object）
- key_levels（object）
- anomalies（array[string]）
- summary（string）

实现：[contracts.py](services/market_state_engine/src/contracts.py#L114-L148)

注意：`MarketStateMSL` dataclass 内部存在 `evidence` 字段，但 `to_llm_dict()` **不会输出**该字段（保持对外 MSL 稳定低维）。

### 9.2 字段枚举（强约束）

MSL 的枚举集合以 JSON Schema 为准：[msl.schema.json](services/market_state_engine/docs/msl.schema.json)

#### 9.2.1 market_regime

| 字段 | 枚举 |
|---|---|
| trend | bullish / bearish / sideways / unknown |
| phase | impulse / continuation / exhaustion / accumulation / distribution / unknown |
| timeframe_alignment | aligned / mixed / conflicting / unknown |

`strength` 为 `number >= 0.0`（当前实现为离散映射的浮点值）。

#### 9.2.2 liquidity_state

| 字段 | 枚举 |
|---|---|
| dominant_pressure | buyers / sellers / balanced / unknown |
| liquidity_risk | short_squeeze / long_squeeze / neutral / unknown |
| orderbook_bias | bid_heavy / ask_heavy / neutral / unknown |
| liquidation_proximity | above / below / both / none / unknown |

#### 9.2.3 positioning_state

| 字段 | 枚举 |
|---|---|
| crowding | crowded_long / crowded_short / balanced / unknown |
| whale_bias | long / short / neutral / unknown |
| retail_bias | long / short / neutral / unknown |
| oi_trend | expanding / contracting / flat / unknown |

说明：当前生成器会把 `whale_bias/retail_bias` 固定为 `"unknown"`（尚未接入对应输入）。

#### 9.2.4 volatility_state

| 字段 | 枚举 |
|---|---|
| volatility_regime | low / normal / high / unknown |
| expansion_risk | expanding / compressing / unknown |
| volatility_direction | upside / downside / neutral / unknown |

#### 9.2.5 market_risk_state

| 字段 | 枚举 |
|---|---|
| cascade_risk | high / medium / low / unknown |
| squeeze_probability | high / medium / low / unknown |
| reversal_risk | high / medium / low / unknown |

#### 9.2.6 market_structure_state

| 字段 | 枚举 |
|---|---|
| support_strength | strong / medium / weak / unknown |
| resistance_strength | strong / medium / weak / unknown |
| range_state | breakout / range / breakdown / unknown |
| trend_structure | hh_hl / lh_ll / mixed / unknown |

说明：当前生成器会把 `support_strength/resistance_strength` 固定为 `"unknown"`（尚未接入对应输入）。

---

## 10. 多周期输出：msl_bundle / cross_horizon

当引擎启用多周期推断时，会对 `short_term/mid_term/long_term` 依次构造“视图映射”并分别推断 MSL：

- `msl_bundle.{hz}`：每周期的 `msl.to_llm_dict()` 输出
- `msl_bundle_meta.{hz}`：每周期对应的 `msl_meta`

实现：[engine.py](services/market_state_engine/src/engine.py#L388-L397)

### 10.1 cross_horizon 字段表（强实现约束）

| 字段 | 类型 | 枚举/范围 | 含义 |
|---|---|---|---|
| alignment | string | aligned / mixed / conflicting / unknown | 多周期一致性摘要 |
| conflicts | array[object] | 见下 | 冲突明细（只记录 conflicting） |
| suggested_policy | string | follow_long_term / wait_confirmation / reduce_risk / no_action | 策略建议（仅提示，不是交易动作） |
| policy_reason | string | 见实现 | suggested_policy 命中原因 |

实现：[engine.py](services/market_state_engine/src/engine.py#L299-L387)

### 10.2 conflicts 元素结构

每个冲突元素（object）字段：

| 字段 | 类型 | 含义 |
|---|---|---|
| field | string | 冲突字段名（仅以下 4 个） |
| short_term | string | 短周期该字段值（unknown 兜底） |
| mid_term | string | 中周期该字段值 |
| long_term | string | 长周期该字段值 |

`field` 允许值与优先级（高->低）：

1. trend
2. phase
3. volatility_regime
4. liquidity_risk

---

## 11. 最终响应：GET /internal/market-state/{exchange}/{symbol}

### 11.1 正常响应（status=ok）

响应字段集合（顶层）：

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| exchange | string | Y | 交易所 |
| symbol | string | Y | 交易对 |
| status | string | Y | 固定 `"ok"` |
| msl | object | Y | MSL（见 9） |
| state_features | object | Y | MarketStateFeatures.to_dict()（见 5） |
| anomaly_flags | array[string] | Y | 用于 UI/告警的异常标签集合（见 12） |
| msl_meta | object | Y | 推断元信息（见 8.2） |
| msl_bundle | object | Y | 多周期 MSL（可为空） |
| msl_bundle_meta | object | Y | 多周期 meta（可为空） |
| cross_horizon | object | Y | 多周期一致性摘要（见 10） |
| raw_market_structure | object | Y | 清洗后的上游原始结构（审计/调试） |
| ts | int | Y | 响应生成时间戳（ms） |
| ts_ms | int | Y | 同 ts（兼容字段） |

组装实现：[service.py](services/market_state_engine/src/service.py#L316-L328) 与 [routes.py](services/market_state_engine/src/routes.py#L33-L38)

### 11.2 短路响应（status=data_unavailable）

当上游 `feature_service` 显式返回 `feature_data_unavailable` 时，Service 返回 HTTP 200，但响应体标记为不可用并填充兜底结构：

额外字段：

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| reason_code | string | Y | 固定 `"feature_data_unavailable"` |
| degraded_reasons | array[string] | Y | 上游给出的降级原因列表 |

短路结构构造：[service.py](services/market_state_engine/src/service.py#L83-L168)

---

## 12. anomaly_flags 总表（当前实现可出现的所有标签）

### 12.1 引擎（detect_anomalies）产生

- orderbook_liquidity_vacuum：订单簿流动性真空
- oi_spike：OI 变化过大
- liquidation_cluster：清算簇/脆弱杠杆迹象
- leverage_extreme：杠杆极端
- crowding_extreme：拥挤度极端

来源：[engine.py](services/market_state_engine/src/engine.py#L190-L221)

### 12.2 Service（输入守卫/selected events/降级）附加

- external_event_input_ignored：输入包含外部事件域字段，已被剔除
- selected_event_context_attached：已融合 selected events 上下文
- selected_events_unavailable：读取 selected events 失败，已降级忽略
- selected_events_unversioned：selected events 存在缺失 `trace.schema_version` 的项
- data_unavailable：上游关键结构不可用导致短路

来源：[service.py](services/market_state_engine/src/service.py#L84-L168) 与 [service.py](services/market_state_engine/src/service.py#L272-L309)

---

## 13. 运行期环境变量（与实现对齐）

### 13.1 上游 raw structure

| 变量 | 默认值 | 含义 |
|---|---|---|
| RAW_STRUCTURE_PROVIDER_URL | http://127.0.0.1:9961 | 上游 feature_service base URL |
| RAW_STRUCTURE_PROVIDER_TIMEOUT_S | 10 | HTTP 超时（秒） |

来源：[app.py](services/market_state_engine/src/app.py#L16-L22)

### 13.2 selected events（可选）

| 变量 | 默认值 | 含义 |
|---|---|---|
| MSE_SELECTED_EVENT_PROVIDER_MODE | none | 取值 `none/redis` |
| MSE_SELECTED_EVENT_REDIS_URL | redis://127.0.0.1:6379/0 | Redis 连接串 |
| MSE_SELECTED_EVENT_STREAM | ec:selected | Stream key |
| MSE_SELECTED_EVENT_LIMIT_DEFAULT | 20 | 默认返回条数 |
| MSE_SELECTED_EVENT_SCAN_FACTOR | 5 | 扫描倍率（实际扫描 count = limit * factor） |

来源：[app.py](services/market_state_engine/src/app.py#L23-L37)

### 13.3 state_inference 插件配置

| 变量 | 默认值 | 含义 |
|---|---|---|
| MSE_STATE_PLUGIN_PROFILE | default | profile：default/fast_mode/risk_only |
| MSE_STATE_PLUGIN_PROFILES_FILE | "" | 自定义 profiles JSON 文件路径（可为空） |
| MSE_MSL_INFERENCE_VERSION | msl_generator_v1 | 生成器版本：msl_generator_v1/v2 |
| MSE_STATE_PLUGINS_ENABLED | "" | 仅启用插件列表（CSV） |
| MSE_STATE_PLUGINS_DISABLED | "" | 禁用插件列表（CSV） |

来源：[service.py](services/market_state_engine/src/service.py#L58-L81)

---

## 14. 模块边界（职责声明）

`market_state_engine` 的职责：
- 消费上游 raw structure（结构类输入），聚合 features
- 识别 anomalies / regime
- 产出面向下游消费的 MSL（稳定低维语义层）
- 当上游显式不可用时短路并返回 `status=data_unavailable`
- 忽略/拒绝混入的外部事件域输入（news/social/onchain/...）

不负责：
- 采集原始市场数据、指标计算
- 外部事件流的 dedup/classify/prioritize（那是 `event_center_new` 的职责）
- 输出交易动作（那是 `agent_server_new` 的职责）

来源：[boundaries.md](services/market_state_engine/docs/boundaries.md)
