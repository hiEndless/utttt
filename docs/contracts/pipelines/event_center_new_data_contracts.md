# event_center_new 数据环节字段契约（实现对齐版）

本文档面向 `/services/event_center_new` 当前代码实现，按流水线各环节（Raw/Normalized/Evidence/Context/L0/L1/FinalGate/Selected）梳理输入输出字段约定、枚举值与解释，并补充 Redis 分层写入格式与运行期配置。

时间语义说明（重要）：
- 流水线内部执行字段仍以 `ts_ms` 为主（兼容历史实现）。
- `SelectedEvent` 对外契约已预留双时间语义：`event_ts_ms`（发生时间）与 `processed_ts_ms`（处理时间）。
- 过渡期保留 `ts_ms`，仅作为兼容别名，不建议新增下游仅依赖 `ts_ms`。

主要依据：
- 数据结构定义：[ec/contracts.py](services/event_center_new/ec/contracts.py)
- 流水线执行顺序：[ec/pipeline/runner.py](services/event_center_new/ec/pipeline/runner.py)
- 默认 stages 实现：[ec/pipeline/defaults.py](services/event_center_new/ec/pipeline/defaults.py)
- Redis 分层写入格式：[ec/storage/redis.py](services/event_center_new/ec/storage/redis.py)
- 运行期环境变量表：[docs/runtime.md](services/event_center_new/docs/runtime.md)
- 概念性 schema 文档（建议语义）：[docs/schema.md](services/event_center_new/docs/schema.md)

---

## 0. 总览：流水线的“真实执行顺序”

`EventPipelineRunner._process_event()` 的核心顺序如下（对应每层输出落盘）：

1. Raw：写入 `EventEnvelope`（原始事件）
2. Normalized：`Normalizer.normalize(EventEnvelope) -> EventEnvelope`
3. Evidence：`EvidenceExtractor.extract(EventEnvelope) -> list[Evidence]`
4. EventMemory：`put(new evidences)` + `get_active_evidences()`（按 TTL 取滑窗）
5. Correlation：`CorrelationEngine.correlate(active evidences) -> list[Evidence]`
6. Context：`ContextBuilder.build(ts_ms, asset, evidences) -> EventContextSnapshot`
7. L0：`L0Processor.process(context) -> ClassifiedEvent`
8. L1：`L1Aggregator.aggregate(context, l0) -> PrioritizedEvent`
9. FinalGate：`FinalGate.emit(context, l0, l1, trigger_event) -> SelectedEvent | None`

参考实现：[runner.py](services/event_center_new/ec/pipeline/runner.py#L120-L150)

---

## 1. 全局枚举与基础约束

这些枚举值在代码层已经固定（`typing.Literal`），属于强约束输入输出：

### 1.1 EventKind（事件层级）
定义：`EventKind = "strategic" | "tactical" | "trigger"`  
来源：[contracts.py](services/event_center_new/ec/contracts.py#L7)

- strategic：偏长期/宏观/结构性信息（小时～天级影响），通常用于“背景约束/风险标签/长周期证据”
- tactical：中期战术证据（分钟～小时），可影响方向倾向与优先级
- trigger：短期触发（秒～分钟），多用于“触发关注/触发路由”，不一定直接等价“交易动作”

### 1.2 Direction（方向）
定义：`Direction = "bullish" | "bearish" | "neutral" | "mixed"`  
来源：[contracts.py](services/event_center_new/ec/contracts.py#L8)

- bullish：偏多
- bearish：偏空
- neutral：中性/无方向
- mixed：混合/冲突（同类证据存在多空对冲或窗口一致性不足）

在默认实现里：
- EvidenceExtractor 会把非法值纠正为 `neutral`（[defaults.py](services/event_center_new/ec/pipeline/defaults.py#L38-L43)）
- L0 会在多空差值较小或总分过低时输出 `mixed/neutral`（[defaults.py](services/event_center_new/ec/pipeline/defaults.py#L86-L93)）

### 1.3 Horizon（作用周期）
定义：`Horizon = "short" | "mid" | "long"`  
来源：[contracts.py](services/event_center_new/ec/contracts.py#L9)

- short：短周期（秒～十几分钟）
- mid：中周期（几十分钟～数小时）
- long：长周期（小时～天）

默认 EvidenceExtractor 会把非法值纠正为 `short`（[defaults.py](services/event_center_new/ec/pipeline/defaults.py#L41-L43)）。

### 1.4 Priority（优先级）
定义：`Priority = "low" | "medium" | "high"`  
来源：[contracts.py](services/event_center_new/ec/contracts.py#L10)

- low：低优先级（可能仅用于背景/状态层融合）
- medium：中优先级（可进入下游策略层）
- high：高优先级（更可能触发下游动作或需要关注）

默认 L0 根据 evidence 总分阈值给出 priority（[defaults.py](services/event_center_new/ec/pipeline/defaults.py#L93-L104)）。

---

## 2. 分层写入（Redis / Memory）的统一字段约定

### 2.1 Redis Stream entry 格式（强约束）
当启用 `RedisLayerStore` 时，每条写入都是一次 `XADD`，字段固定为：

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| payload | string(JSON) | Y | 对象整体 JSON 序列化 |
| ts_ms | string | Y | 从 payload 中取 `ts_ms`，写入为字符串，便于快速筛选/回放 |

来源：[ec/storage/redis.py](services/event_center_new/ec/storage/redis.py#L62-L65)

注意：
- `payload` 内部才是 Raw/Normalized/Evidence/Context/Selected 的真实结构。
- stream 名称可通过环境变量覆盖，默认值见 [docs/runtime.md](services/event_center_new/docs/runtime.md#L15-L34)。

### 2.2 分层 streams（默认 key）

| 层 | 默认 stream | 写入内容 |
|---|---|---|
| raw | ec:raw | EventEnvelope（原始输入事件） |
| normalized | ec:normalized | EventEnvelope（标准化后事件） |
| evidence | ec:evidence | Evidence（单条证据，多条逐条写入） |
| context | ec:context | EventContextSnapshot（上下文快照） |
| selected | ec:selected | SelectedEvent（下游消费的最终产物） |

来源：[RedisLayerStoreConfig](services/event_center_new/ec/storage/redis.py#L17-L25)

### 2.3 健康信号 key（KV）
健康快照不走 stream，走 Redis KV（便于运维直接 GET）：
- key 默认：`ec:runner:health`（可通过 `EVENT_CENTER_HEALTH_KEY` 覆盖）
- value：JSON 字符串

来源：[ec/storage/redis.py](services/event_center_new/ec/storage/redis.py#L58-L61) 与 [docs/runtime.md](services/event_center_new/docs/runtime.md#L86-L104)

---

## 3. Raw 层（输入：EventEnvelope）

### 3.1 Raw 输入来源（EventSourceAdapter.poll）
Runner 每轮对每个 source 调用：
- `poll(cursor) -> (events: list[EventEnvelope], next_cursor)`

接口定义：[ec/sources/base.py](services/event_center_new/ec/sources/base.py#L9-L19)

当前代码自带的 source 仅有 `InMemoryEventSource`（demo/测试用途）：
- 它不会从外部拉取，只是把预置 events 一次性吐出（[ec/sources/memory.py](services/event_center_new/ec/sources/memory.py#L15-L20)）。

### 3.2 EventEnvelope 字段表（实现强约束）
数据结构：[EventEnvelope](services/event_center_new/ec/contracts.py#L28-L43)

| 字段 | 类型 | 必填 | 枚举/范围 | 含义与约定 |
|---|---|:---:|---|---|
| id | str | Y | 建议 ULID/UUID | 事件唯一标识；不建议承载业务语义 |
| ts_ms | int | Y | 毫秒时间戳 | 事件发生时间；用于 recency / window / 去重与回放窗口 |
| asset | str | Y | 示例 ETHUSDT | 资产/标的；下游消费与 EventMemory 分组的主 key |
| kind | EventKind | Y | strategic/tactical/trigger | 事件层级；影响 ttl 与路由策略 |
| type | str | Y | 自定义字符串 | 事件类型（命名规范建议 `domain.subtype`） |
| source | EventSource | Y | 见 3.3 | 事件来源摘要（name/category） |
| importance | float | Y | 0~1 | 先验重要性；默认评分会参与 evidence score |
| ttl_ms | int | Y | ≥0 | 生命周期；EventMemory 用它决定过期时间 |
| payload | dict | Y | JSON object | 原始内容或结构化内容；默认 EvidenceExtractor 读取 `payload.evidences` |
| exchange | str\|None | N | 如 binance | 交易所；可为空（非交易所事件） |
| account_id | str\|None | N | 如 main | 账号；是否必需由上游决定 |
| meta | dict | N | JSON object | 可选元信息（解析版本/语言/采样率等） |
| trace | EventTrace | N | 见 3.4 | 追踪字段（去重/关联/版本） |

### 3.3 EventSource 字段表
数据结构：[EventSource](services/event_center_new/ec/contracts.py#L13-L17)

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| name | str | Y | 来源系统/组件名（如 feature_service/coinglass/twitter/internal） |
| category | str | Y | 来源类别（建议有限集合，如 technical/news/onchain/social/orderbook/liquidation） |

### 3.4 EventTrace 字段表
数据结构：[EventTrace](services/event_center_new/ec/contracts.py#L19-L26)

| 字段 | 类型 | 必填 | 含义与约定 |
|---|---|:---:|---|
| dedup_key | str\|None | N | 幂等去重键（同一语义事件应保持稳定）；建议 normalized 阶段产出 |
| correlation_id | str\|None | N | 关联 ID（跨来源/跨阶段把同一故事串起来） |
| parent_id | str\|None | N | 父事件 ID（例如聚合事件引用原始事件） |
| produced_by | str\|None | N | 生产者（组件名） |
| schema_version | str\|None | N | schema 版本（下游消费侧用于兼容与审计） |

---

## 4. Normalized 层（输出：EventEnvelope）

### 4.1 Normalizer 接口
接口定义：[ec/pipeline/stages.py](services/event_center_new/ec/pipeline/stages.py#L16-L18)

- 输入：EventEnvelope（raw）
- 输出：EventEnvelope（normalized）

### 4.2 当前默认实现：透传（PassThroughNormalizer）
默认实现只是 `return event`，不会补齐任何字段（[defaults.py](services/event_center_new/ec/pipeline/defaults.py#L19-L23)）。

因此“字段约定”的现实含义是：
- 你期望 normalized 满足的稳定语义，需要在未来替换 Normalizer 实现来完成（比如生成 `trace.dedup_key`、规范化 asset/type/source/category、裁剪 payload 等）。
- 现阶段 raw 与 normalized 在数据结构上完全相同，只是分层落盘不同。

---

## 5. Evidence 层（输出：Evidence）

### 5.1 EvidenceExtractor 接口
接口定义：[ec/pipeline/stages.py](services/event_center_new/ec/pipeline/stages.py#L21-L23)

- 输入：EventEnvelope（normalized）
- 输出：list[Evidence]

注意：分层落盘时是一条 Evidence 写一次 `ec:evidence`（[runner.py](services/event_center_new/ec/pipeline/runner.py#L125-L128)）。

### 5.2 Evidence 字段表（实现强约束）
数据结构：[Evidence](services/event_center_new/ec/contracts.py#L45-L59)

| 字段 | 类型 | 必填 | 枚举/范围 | 含义与约定 |
|---|---|:---:|---|---|
| ts_ms | int | Y | 毫秒时间戳 | 证据观测时间；用于 recency_decay |
| type | str | Y | 自定义字符串 | 证据类型；建议有限集合/命名空间化 |
| direction | Direction | Y | bullish/bearish/neutral/mixed | 证据方向倾向 |
| strength | float | Y | 0~1 | 强度（越大越值得纳入上下文 Top-K） |
| horizon | Horizon | Y | short/mid/long | 作用周期 |
| ttl_ms | int | Y | ≥0 | 证据有效期；EventMemory 以此裁剪 |
| importance | float | Y | 0~1 | 重要性（通常继承 event.importance） |
| evidence_confidence | float\|None | N | 0~1 | 显式语义字段：证据置信度 |
| confidence | float\|None | N | 0~1 | 兼容字段：与 evidence_confidence 同步 |
| source_refs | list[dict] | N | 列表 | 引用链：证据来自哪些原始来源（建议放 event_id/片段/链接等） |
| attrs | dict | N | JSON object | 附加属性（zscore/计数/关键词等） |

### 5.3 当前默认提取规则：从 payload.evidences 透传
默认 EvidenceExtractor：`PayloadEvidenceExtractor`（[defaults.py](services/event_center_new/ec/pipeline/defaults.py#L26-L65)）

它对输入 `event.payload` 的约定是：

- `event.payload["evidences"]` 必须是 list
- list 内每个元素是 dict，支持字段：
  - `type`（缺省取 `event.type`）
  - `direction`（非法值回落 `neutral`）
  - `strength`（缺省 0）
  - `horizon`（非法值回落 `short`）
  - `ttl_ms`（缺省取 `event.ttl_ms`）
  - `importance`（缺省取 `event.importance`）
  - `evidence_confidence` 或 `confidence`（二选一；最终会同时写入两个字段）
  - `source_refs`（list，否则空）
  - `attrs`（dict，否则空）
  - `ts_ms`（缺省取 `event.ts_ms`）

---

## 6. EventMemory（短期记忆：Evidence 滑动窗口）

### 6.1 作用与读写语义
EventMemory 是“按资产维度维护的 Evidence TTL 滑动窗口”，主要用途：
- 把多条事件的证据在时间窗口内汇总成一个“当前态势证据集”
- 为 correlation/context/L0/L1 提供更稳定输入（不是只看单条事件）

接口定义：[ec/storage/memory.py](services/event_center_new/ec/storage/memory.py#L15-L20)

当前默认实现：`InMemoryEventMemory`：
- `put()`：把 new evidences 按 `asset` 写入，并即时裁剪过期项（[memory.py](services/event_center_new/ec/storage/memory.py#L35-L45)）
- `get_active_evidences(asset, ts_ms)`：返回 `expire_at_ms > ts_ms` 的 evidences（[memory.py](services/event_center_new/ec/storage/memory.py#L46-L51)）

### 6.2 过期时间计算（强约束）
- `expire_at_ms = evidence.ts_ms + max(0, evidence.ttl_ms)`（[memory.py](services/event_center_new/ec/storage/memory.py#L40-L42)）

---

## 7. Correlation（证据关联合成）

### 7.1 输入输出
- 输入：active evidences（EventMemory 返回）
- 输出：合成后的 evidences（保留 remaining + synthesized）

核心实现：[CorrelationEngine.correlate](services/event_center_new/ec/correlation/rules.py#L66-L76)

### 7.2 SimpleClusterRule 字段表
结构：[SimpleClusterRule](services/event_center_new/ec/correlation/rules.py#L20-L59)

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| a_type | str | Y | 触发条件 A evidence.type |
| b_type | str | Y | 触发条件 B evidence.type |
| out_type | str | Y | 合成 evidence.type |
| out_direction | Direction | Y | 合成方向（显式配置） |
| out_horizon | Horizon | Y | 合成周期（显式配置） |
| suppress_inputs | bool | N | 是否抑制输入类型（把 a_type/b_type 从 remaining 中移除） |

合成 Evidence 的规则要点：
- `ts_ms` 取两者 max
- `strength` 取两者均值（并做上限）
- `ttl_ms` 取两者 min（合成证据不应比输入活得更久）
- `importance` 取 max（并做上限）
- `confidence` 取两者均值（并做上限）
- `source_refs` 记录两个输入的 `{type, ts_ms}`（[rules.py](services/event_center_new/ec/correlation/rules.py#L42-L56)）

---

## 8. Context 层（输出：EventContextSnapshot）

### 8.1 EventContextSnapshot 字段表（实现强约束）
数据结构：[EventContextSnapshot](services/event_center_new/ec/contracts.py#L61-L69)

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| ts_ms | int | Y | 上下文快照生成时间（当前用 normalized.ts_ms） |
| asset | str | Y | 标的（用于下游消费与路由） |
| key_evidences | list[Evidence] | Y | 重要证据 Top-K（含 horizon 分桶策略） |
| active_triggers | list[dict] | N | 近期触发摘要（当前取最近 5 条 evidence 的 type/direction/ts_ms） |
| conflicts | list[dict] | N | 冲突摘要（当前实现：同 type 出现 bullish 与 bearish） |
| tags | list[str] | N | 标签集合（当前实现：has_conflict/has_{horizon}_horizon） |
| alternative_sources_summary | dict | N | news/social/onchain 来源摘要（available/provider_states/data_sources/inference_sources/feature_keys/evidence_counts） |

`alternative_sources_summary.provider_states` 枚举口径（event_center）：
- `event_evidence_present`
- `empty`

统一策略单源：`contracts/semantic_policies/source_semantics.yaml`

### 8.2 ContextBuilder 的输入输出
输入结构：`ContextBuildInput(ts_ms, asset, evidences, last_context=None)`（[context/builder.py](services/event_center_new/ec/context/builder.py#L11-L17)）

当前实现：`DefaultContextBuilder`：
- 对每条 Evidence 做统一评分（PriorityScorer）
- 按 horizon 分桶后做 Top-K（BucketTopKPolicy）
- 生成 conflicts/tags/active_triggers（[builder.py](services/event_center_new/ec/context/builder.py#L36-L51)）

### 8.3 Evidence 评分公式（用于 Top-K）
`PriorityScorer.score_evidence()`（[scorer.py](services/event_center_new/ec/prioritization/scorer.py#L30-L39)）

- 置信度字段选取顺序：`evidence_confidence` 优先，否则用 `confidence`，都没有则视为 1.0
- 置信度下限：`min_confidence` 默认 0.2
- 时间衰减：指数半衰期 `half_life_ms` 默认 15min（`exp(-ln(2)*age/half_life)`）
- 最终：`score = importance * strength * confidence * recency_decay`

---

## 9. L0（Classify）层（输出：ClassifiedEvent）

### 9.1 ClassifiedEvent 字段表（实现强约束）
数据结构：[ClassifiedEvent](services/event_center_new/ec/contracts.py#L71-L83)

| 字段 | 类型 | 必填 | 枚举/范围 | 含义 |
|---|---|:---:|---|---|
| asset | str | Y |  | 标的 |
| ts_ms | int | Y |  | 分类时间（当前用 context.ts_ms） |
| confirmed_direction | Direction | Y | bullish/bearish/neutral/mixed | 分类后的方向确认 |
| score | float | Y | ≥0 | 窗口总分（默认实现是 key_evidences 的加权和） |
| confidence | float | Y | 0~1 | 分类置信度（默认：abs(diff)/total） |
| priority | Priority | Y | low/medium/high | 基于 score 阈值的优先级 |
| classification_confidence | float | N | 0~1 | 显式语义字段（当前等同 confidence） |
| window | dict | N | JSON object | 窗口统计摘要（当前只有 evidence_count） |
| reasons | list[str] | N | 结构化原因码（当前默认空） |

### 9.2 默认实现：HeuristicL0Processor
规则要点（[defaults.py](services/event_center_new/ec/pipeline/defaults.py#L70-L105)）：
- 每条 evidence 的贡献：`strength * importance * confidence`
- mixed 方向会按 0.5 分摊到 bull/bear
- 方向判定：
  - total <= 0 → neutral
  - abs(diff) <= max(0.05, total*0.15) → mixed
  - 否则 diff>0 bullish，diff<0 bearish
- priority 阈值：total>=1.2 high，>=0.5 medium，否则 low

---

## 10. L1（Prioritize）层（输出：PrioritizedEvent）

### 10.1 PrioritizedEvent 字段表（实现强约束）
数据结构：[PrioritizedEvent](services/event_center_new/ec/contracts.py#L85-L95)

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| asset | str | Y | 标的 |
| ts_ms | int | Y | 时间（当前用 context.ts_ms） |
| classification | str | Y | 分类标签（当前实现：mixed → conflict，否则 directional） |
| component_scores | dict | Y | 解释性分数（当前只含 l0_score/l0_confidence/conflict_count 等） |
| key_evidences | list[Evidence] | Y | 透传 context.key_evidences（可裁剪策略放此层实现） |
| conflicts | list[dict] | N | 透传 context.conflicts |
| routing_hints | dict | N | 路由提示（当前默认空） |
| priority | Priority | N | 供 FinalGate 使用的优先级（当前等同 l0.priority） |

### 10.2 默认实现：HeuristicL1Aggregator
实现：[defaults.py](services/event_center_new/ec/pipeline/defaults.py#L107-L129)

当前 component_scores 字段约定：
- l0_score：float
- l0_confidence：float
- classification_confidence：float
- conflict_count：int

---

## 11. FinalGate（Select）层（输出：SelectedEvent）

### 11.1 SelectedEvent 字段表（实现强约束）
数据结构：[SelectedEvent](services/event_center_new/ec/contracts.py#L97-L108)

| 字段 | 类型 | 必填 | 枚举/范围 | 含义 |
|---|---|:---:|---|---|
| asset | str | Y |  | 标的 |
| ts_ms | int | Y |  | 兼容时间别名（当前用 context.ts_ms） |
| event_ts_ms | int\|None | N |  | 事件发生时间（优先来自 trigger_event.ts_ms） |
| processed_ts_ms | int\|None | N |  | 系统处理/选出时间（当前等于 context.ts_ms） |
| selected_type | str | Y | 默认 event.selected | 选出事件类型（下游消费侧的“事件大类”） |
| direction_hint | Direction | Y | bullish/bearish/neutral/mixed | 方向提示（不等价交易结论） |
| priority | Priority | Y | low/medium/high | 最终优先级 |
| context_snapshot | EventContextSnapshot | Y |  | 下游消费的证据快照 |
| trigger_event | EventEnvelope\|None | N |  | 触发事件（当前透传 normalized） |
| source | EventSource\|None | N |  | 来源摘要（当前透传 trigger_event.source） |
| trace | EventTrace\|None | N |  | 追踪字段（至少应带 schema_version） |
| route | dict | N |  | 下游路由控制（见 11.2） |

补充约束（跨服务契约建议）：
- 下游 freshness/排序语义优先使用 `event_ts_ms`，再回退 `ts_ms`。
- 审计与处理延迟评估优先使用 `processed_ts_ms`。

### 11.2 route 字段约定（当前默认实现）
默认 FinalGate 会生成如下 route（[defaults.py](services/event_center_new/ec/pipeline/defaults.py#L149-L160)）：

| route key | 类型 | 默认值 | 含义 |
|---|---|---:|---|
| to_market_state_engine | bool | true | 是否路由到状态层消费者（market_state_engine） |
| to_agent_server_new | bool | true | 是否路由到决策层消费者（agent_server_new） |
| review_required | bool | false | 是否需要人工/人工策略复核（通常用于 mixed） |
| mixed_policy | str | 可选 | mixed 时的策略标记（当前为 degrade_and_route_state_only） |

当 `direction_hint == "mixed"` 时，默认 gate 的特殊策略：
- 若 `l0.score < mixed_min_score` 或 `key_evidences 数 < mixed_min_evidences` → 直接丢弃不输出
- 否则：
  - priority 降级为 `mixed_output_priority`（默认 low）
  - `review_required=true`
  - `to_agent_server_new=false`（只路由状态层）
  - `mixed_policy="degrade_and_route_state_only"`

对应配置结构：`SelectPolicyConfig(mixed_min_score=0.25, mixed_min_evidences=2, mixed_output_priority="low")`（[defaults.py](services/event_center_new/ec/pipeline/defaults.py#L131-L136)）。

### 11.3 trace 字段约定（selected-v2）
默认 FinalGate 会构造：
- `EventTrace(schema_version="selected-v2", produced_by="event_center_new")`
- 若 trigger_event.trace 存在，则优先透传其字段，并补齐 produced_by/schema_version 的默认值（[defaults.py](services/event_center_new/ec/pipeline/defaults.py#L161-L170)）。

这意味着：
- 下游消费 `ec:selected` 时应优先关注 `trace.schema_version`
- 上游 normalized 若能生成稳定的 dedup_key/correlation_id/parent_id，将直接贯穿到 selected，便于幂等与链路追踪

---

## 12. 运行期配置与“层”的切换

### 12.1 分层存储模式
`EVENT_CENTER_LAYER_STORE_MODE`：
- memory：仅内存存储（适合本地调试）
- redis：写入 Redis 分层 stream（适合联调/回放/CI）

详见：[docs/runtime.md](services/event_center_new/docs/runtime.md#L15-L34)

### 12.2 运行模式（单次/循环/自检）
Runner 本身不是“定时拉特征数据”，它是“轮询事件源、处理事件”：
- 自检：`EVENT_CENTER_SELF_CHECK_ONLY=true` → 只写健康信号后退出
- 单次：`EVENT_CENTER_RUN_LOOP=false` → 执行一次 `run_once`
- 循环：`EVENT_CENTER_RUN_LOOP=true` → 每 `EVENT_CENTER_RUN_INTERVAL_MS` 运行一轮

入口实现：[main.py](services/event_center_new/main.py#L94-L127)

---

## 13. 下游消费最小注意事项（与本仓库消费者对齐）

虽然本文件聚焦 event_center_new，但为了保证“字段约定能落地”，这里补充当前仓库下游消费侧的硬约束（便于你在设计字段时不踩坑）：

- 下游（market_state_engine / agent_server_new）消费 `ec:selected` 时是从 stream entry 的 `payload` 字段反序列化 JSON，而不是直接拿 stream field 做业务（参考：[ec/storage/redis.py](services/event_center_new/ec/storage/redis.py#L62-L65)）。
- 下游会基于 `asset` 做精确匹配（通常是 `exchange:symbol` 或 `symbol` 规范），因此 `asset` 必须稳定、不可随意变形。
- `trace.schema_version` 是兼容升级的关键字段，应尽量保证存在且可审计。
