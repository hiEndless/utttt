# 事件契约与字段规范（v2）

本文定义新的事件中心端到端字段语义：`raw → normalized → evidence → context_snapshot → classify → prioritize → select`。

目标：字段少而稳定、语义单一、可演进、可做幂等与可观测性。

---

## 1. 基础概念

### 1.1 EventEnvelope（事件信封）

EventEnvelope 是系统内传递的最小统一单位，任何来源（指标、爆仓、新闻、链上、社媒等）进入系统后必须先变成 EventEnvelope。

建议字段（核心字段尽量固定，不随来源变化）：

| 字段 | 类型 | 必填 | 说明 |
|---|---:|:---:|---|
| id | str | Y | 事件主键，建议 ULID/UUID，不承载业务语义 |
| ts_ms | int | Y | 事件发生时间（毫秒） |
| exchange | str | N | 交易所（如 binance），非交易所来源可为空或填 `global` |
| account_id | str | N | 账号标识（若与用户强绑定） |
| asset | str | Y | 资产/标的（如 BTCUSDT / BTC），统一规范由上游 adapter 负责 |
| kind | str | Y | strategic / tactical / trigger |
| type | str | Y | 事件类型（如 `news.regulatory` / `liquidation.cluster` / `onchain.exchange_inflow` / `technical.indicator_signal`） |
| source_name | str | Y | 来源名称（如 coinglass / twitter / internal.indicators） |
| source_category | str | Y | technical / liquidation / news / onchain / social / orderbook / mixed |
| importance | float | Y | 0~1 重要性（与 source/类型相关的先验权重） |
| ttl_ms | int | Y | 生命周期（毫秒），到期后从 EventMemory 中移除 |
| payload | dict | Y | 原始内容或结构化内容（可包含原始文本、原始数值、引用链接等） |
| meta | dict | N | 可选元信息（如语言、采样率、解析版本） |
| trace | dict | N | 追踪字段（dedup_key/correlation_id/parent_id/produced_by/schema_version 等） |

### 1.2 Evidence（证据）

Evidence 是从 EventEnvelope 中提炼出的“可用于决策/聚合”的结构化特征。系统不鼓励把原始事件直接向下游传播为背景信息，而是提炼为 Evidence 并压缩。

建议字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---:|:---:|---|
| ts_ms | int | Y | 证据对应的观测/提取时间（用于 recency_decay） |
| type | str | Y | 证据类型（如 `liquidation_cluster` / `exchange_inflow_spike` / `macro_regulatory_uncertainty`） |
| direction | str | Y | bullish / bearish / neutral / mixed |
| strength | float | Y | 0~1 强度（越大越值得纳入上下文） |
| horizon | str | Y | short / mid / long |
| ttl_ms | int | Y | 证据生命周期，通常小于或等于 event.ttl_ms |
| importance | float | Y | 0~1 重要性（通常继承自 event.importance） |
| confidence | float | N | 0~1 置信度（尤其适用于新闻/社媒） |
| source_refs | list[dict] | N | 证据引用了哪些原始 event（id/来源/片段） |
| attrs | dict | N | 额外属性（如 zscore、计数、主题、关键词等） |

### 1.3 EventContextSnapshot（事件上下文快照）

EventContextSnapshot 是“给下游使用的事件压缩快照”，它由 Evidence 聚合得到，不包含高噪声原始列表。

建议字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---:|:---:|---|
| ts_ms | int | Y | 上下文快照生成时间 |
| asset | str | Y | 标的 |
| key_evidences | list[Evidence] | Y | 重要证据 Top-K（可按 horizon 分桶） |
| active_triggers | list[dict] | N | 近期触发事件摘要（只保留少量） |
| conflicts | list[dict] | N | 冲突信息（同类 evidence 的多空对冲、强度差等） |
| tags | list[str] | N | 事件标签（供下游路由与检索） |

---

## 2. 流水线阶段与输出契约

### 2.1 raw（原始入口）

raw 阶段只负责把外部输入统一封装成 EventEnvelope，禁止在 raw 阶段做复杂推断与聚合。

输出：`EventEnvelope`

### 2.2 normalized（标准化）

标准化阶段把不同来源 payload 对齐为稳定字段集，输出仍是 EventEnvelope，但要求：
- `asset/type/kind/source_category/importance/ttl_ms` 语义完整
- `trace.dedup_key` 产出

输出：`EventEnvelope (normalized)`

### 2.3 evidence（证据提取）

EvidenceExtractor 为每类 source_category/type 提供提炼逻辑：
- 规则型（指标/爆仓簇/链上阈值）优先
- 需要语义理解（新闻/社媒）可用 LLM，但输出必须是 Evidence，而不是原文

输出：`list[Evidence]`

### 2.4 context_snapshot（上下文构建）

ContextBuilder 聚合 Evidence，完成：
- TTL 过滤
- 重要性/强度/置信度排序
- recency_decay 时间衰减（避免旧证据长期占据 Top-K）
- 冲突消解与净强度计算
- 压缩输出（Top-K + buckets）

输出：`EventContextSnapshot`

### 2.5 classify（确认/去噪）

classify 不处理“插件实现细节”，只处理标准化后的 `direction/strength/horizon` 等稳定字段（来自 Evidence/normalized）。

建议输出字段：

| 字段 | 类型 | 说明 |
|---|---:|---|
| confirmed_direction | str | bullish/bearish/neutral |
| score | float | 0~1 |
| confidence | float | 0~1（来自窗口一致性） |
| priority | str | low/medium/high |
| window | dict | 近 N 个输入的统计摘要 |
| reasons | list[str] | 结构化原因码（避免自由文本） |

### 2.6 prioritize（结构聚合与排序）

prioritize 面向“多源证据”做结构聚合与排序，输出与事件快照强关联：

| 字段 | 类型 | 说明 |
|---|---:|---|
| component_scores | dict | 按 bucket/source_category 的解释分数 |
| key_evidences | list[Evidence] | 聚合后的 Top-K |
| conflicts | list[dict] | 冲突摘要 |
| priority | str | 供 final gate 使用 |

### 2.7 select（路由/去抖/触发）

select 阶段只做“是否输出”与“输出给谁”，不做市场状态推断。

建议输出字段：

| 字段 | 类型 | 说明 |
|---|---:|---|
| selected_type | str | 如 `market.structure_event` / `macro.trigger_event` |
| asset | str | 标的 |
| ts_ms | int | 时间 |
| direction_hint | str | `bullish/bearish/neutral/mixed`，事件方向倾向（非交易结论） |
| priority | str | 低/中/高 |
| context_snapshot | EventContextSnapshot | 下游消费的快照（可裁剪字段） |
| trigger_event | EventEnvelope | 若为触发型输出，附带触发事件摘要 |
| source | object/null | 来源摘要（`name/category`），默认透传 trigger_event.source |
| trace | object | 追踪摘要（`schema_version` 必填），默认透传 trigger_event.trace |
| route | dict | 下游路由（agent/rules/alerts 等） |

契约文件：

- `services/event_center_new/docs/selected_event.schema.json`
- `services/event_center_new/docs/replay_summary.schema.json`（`replay_main --summary-only` 输出）

---

## 3. 事件分层建议（kind 与 ttl_ms）

| kind | 典型来源 | 进入上下文方式 | ttl 建议 |
|---|---|---|---|
| strategic | 宏观/监管/战争/利率 | 作为长期证据进入 key_evidences | 小时～天 |
| tactical | 链上流入/OI/funding 极端 | 进入 key_evidences（中期特征） | 30min～4h |
| trigger | 爆仓簇/突发新闻/社媒热点 | 只作为 trigger_event 或短期 active_triggers | 5min～30min |

---

## 4. 下游透传依据（入库/回放必需）

`SelectedEvent` 在下发时必须携带以下依据字段，确保下游不仅拿到信号，还能拿到证据链：

| 维度 | 字段 | 说明 |
|---|---|---|
| 来源 | `source.name` / `source.category` | 信号来源系统与来源类别 |
| 追踪 | `trace.dedup_key` / `trace.correlation_id` / `trace.parent_id` / `trace.schema_version` | 幂等、关联、父子链路与版本追踪 |
| 条件 | `context_snapshot.key_evidences` / `context_snapshot.conflicts` | 生成信号的证据与冲突摘要 |
| 周期 | `evidence.horizon` / `evidence.ttl_ms` | 生效周期与衰减窗口 |
| 引用 | `evidence.source_refs` | 回指原始事件 ID 与来源 |

---

## 4.1 mixed 方向输出策略（强约束）

当 `direction_hint=mixed` 时：

1. 允许输出到 `SelectedEvent`，但应降级 `priority` 或打 `review_required=true`
2. 必须携带 `context_snapshot.conflicts`，不允许仅给方向不给冲突依据
3. 默认优先路由到状态层融合，不直接当作单边交易触发
4. 仅当满足噪声丢弃条件时可不输出：
   - `importance` 低
   - `strength` 低
   - 证据数量不足或窗口一致性过低

---

## 5. 关联合成与优先级评分依据

### 5.1 关联合成（Correlation）

- 规则型：`a_type + b_type -> out_type`
- 输出方向与周期由规则显式配置：`out_direction/out_horizon`
- 可选抑制输入：`suppress_inputs`

### 5.2 优先级评分（Priority）

当前统一评分公式：

`score = importance * strength * confidence * recency_decay`

- `importance`: 事件先验权重（0~1）
- `strength`: 证据强度（0~1）
- `confidence`: 证据置信度（默认下限 0.2）
- `recency_decay`: 时间衰减（半衰期配置）
