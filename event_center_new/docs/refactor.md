# 重构实施文档 v2（对齐生产级 AI Trading Agent 蓝图）

本文将 `event_center_new` 与 `agent_server_new` 的重构计划对齐到以下生产级蓝图核心链路：

Data Layer → Feature Layer → Event Center → Market State Engine → Decision Agent → Execution Layer

本文聚焦于 **Feature Layer 之后**（不包含数据源 ingest 与底层行情采集的实现细节），并把“可回放 / 可解释 / 可验证”作为阶段性交付物，而非后续补丁。

---

## 0. 范围、边界与成功标准

### 0.1 本文覆盖范围

- `event_center_new/`：实现生产级 Event Center（统一信封、证据、上下文、优先级、去重、相关性、运行时、存储、回放）
- `agent_server_new/`：实现 MarketStateEngine + Single Decision Agent（确定性决策链 + 门控 + 结构化追踪 + 回放）

### 0.2 明确不在本文内的内容

- Data Layer（交易所、链上、新闻/社媒采集系统）的具体接入方式与基础设施选型
- Execution Layer 的交易所下单细节（若现有仓库其他目录已实现，可在本方案第 3 阶段完成对接）

### 0.3 成功标准（最终验收）

- 多源事件统一进入 Event Center，输出稳定 `SelectedEvent/EventWindow`，并可按时间窗重放得到一致的 `select` 输出
- MarketStateEngine 只消费 `selected_event + event_window + deterministic features`，并输出稳定 MSL
- Single Decision Agent 只消费 `signal_event + msl + key_features`，输出结构化 `ExecutionPlan`，且全链路可追踪
- 任意一次线上决策可被复现：输入快照可读、决策链可重放、差异可解释

---

## 1. 现状问题与蓝图缺口（为什么要重构）

旧版 `event_center/` 的结构性痛点是“字段语义不稳定 + 强绑定某类事件形状”，导致新增事件源需要改核心处理器；同时缺少可运行的日志分层与回放工具链，使得“回测/复盘/调参”难以工程化。

重构 v2 的目标是：把系统演进成本从“修改核心处理器”转变为“新增 Adapter/Extractor”，并把 replay 与 explain 变成第一等能力。

---

## 2. 总体架构对齐（蓝图 → 模块归属）

### 2.1 分层与职责

1) Feature Layer（deterministic）
- 输入：raw market data（本文不涉及）
- 输出：market_structure / indicators / derived metrics（可作为 deterministic features）

2) Event Center（系统核心，event_center_new）
- 输入：多源事件（liquidations/indicators/news/onchain/social/宏观等）
- 输出：`SelectedEvent` + `EventWindow`（事件快照：key evidences / conflicts / tags / priority）

3) Market State Engine（世界模型，agent_server_new）
- 输入：deterministic features + selected_event + event_window
- 输出：MSL（Market State Language，稳定语义摘要）

4) Decision Agent（单决策链，agent_server_new）
- 输入：signal_event + MSL + key_market_features（预算控制）
- 输出：ExecutionPlan（动作意图与执行计划）

5) Execution Layer（执行落地）
- 输入：ExecutionPlan
- 输出：真实下单与仓位管理（以及 execution log）

### 2.2 核心原则（必须长期坚持）

- **Event / Evidence / EventWindow 三层分离**：Event=事实与追踪；Evidence=可聚合结构化证据；EventWindow=给下游消费的快照
- **核心处理器只理解稳定字段**：禁止依赖来源 payload 的形状
- **LLM 只能输出结构化结果**：在 Event Center 中，news/social 若接入 LLM，输出必须是 Evidence，而不是原文
- **Single Decision Agent + deterministic modules**：LLM 只做语义裁决，不负责仓位/下单/硬风控
- **Replay-first**：每个阶段都要能落盘与回放，不接受“先跑起来再补日志”

---

## 3. 契约与接口边界（防止耦合与漂移）

### 3.1 契约冻结清单（阶段 0 交付）

必须冻结（版本化 + 校验）以下契约：

- Event Center：
  - `EventEnvelope`
  - `Evidence`
  - `EventContextSnapshot`
  - `SelectedEvent`
- Agent：
  - `MarketStateMSL`
  - `SignalVerdict`
  - `ExecutionPlan`
  - `DecisionTrace`

### 3.2 依赖方向（强约束）

- `event_center_new` **不得** import `agent_server_new`
- `agent_server_new` 通过 port 消费 `selected_event/event_window`（而不是直接 import event center 内部实现）
- 共享契约建议抽到独立模块（例如 `utaker_contracts/`），由两边共同依赖；在拆分前，至少保证“单向依赖 + schema 校验”

### 3.3 端口边界（Ports）

Event Center 必须通过 ports 抽象以下外部依赖：
- Event Source（poll/stream consumer）
- Stream/Storage（raw/normalized/evidence/context/select 写入与查询）
- EventMemory（TTL 事件记忆，支撑 active evidences 与窗口计算）

Agent 必须通过 ports 抽象以下外部依赖：
- FeatureStore/MarketStructure Provider（deterministic features）
- EventWindow Provider（来自 Event Center 的事件快照）
- PositionContext Provider（账户/仓位）
- EventRecorder（决策链日志落地与查询）

---

## 4. 运行时与存储分层（必须可回放）

### 4.1 分层产物（强制落地）

建议按以下分层写入流/存储，命名与职责固定：

- `ec:raw`：原始 `EventEnvelope`
- `ec:normalized`：标准化 `EventEnvelope`（字段语义对齐）
- `ec:evidence`：`Evidence`（单条或批量）
- `ec:context`：`EventContextSnapshot`（Top-K + conflicts + tags）
- `ec:selected`：最终输出（路由/去抖后的信号事件）

### 4.2 幂等与追踪字段（强制要求）

- `id`：ULID/UUID（不承载业务语义）
- `trace.dedup_key`：用于幂等（例如 `exchange|asset|type|bucket_ts|source_name`）
- `trace.correlation_id`：把一组相关事件串起来（例如同一轮触发分析）
- `trace.parent_id`：衍生事件引用其父事件
- `schema_version`：契约版本（必须可验证）

---

## 5. 分阶段实施计划（每阶段可运行、可验收）

### 阶段 0：契约冻结 + 契约校验（Contract Freeze）

目标：
- “新增来源不改核心处理器”所需的稳定契约先落地，并可自动校验

交付物：
- `EventEnvelope/Evidence/EventContextSnapshot/SelectedEvent` 的 schema 版本与校验入口
- `MarketStateMSL/DecisionTrace/ExecutionPlan` 的 schema 版本与校验入口
- 最小的跨模块契约依赖约束说明（依赖方向、禁止 import 规则）

验收标准：
- 任意 EventEnvelope/Evidence/EventContextSnapshot/SelectedEvent 的样例 JSON 可通过校验
- 发生 schema 变更时，校验能明确报错，且能定位字段级差异

---

### 阶段 1：Event Center 可运行闭环（Runtime + Storage v1）

目标：
- event_center_new 具备“输入 → 标准化 → 写入 raw/normalized”闭环，并能按时间窗读取用于重放

交付物：
- Runtime runner（轮询或 stream consumer）能持续产生 `ec:raw` 与 `ec:normalized`
- Storage adapter v1（最小可用：写入 + 按时间窗读取）
- EventMemory 实现 v1（最小可用：TTL put/get_active）

验收标准：
- 给定一段输入事件流（时间窗），可以重放得到相同的 normalized 结果
- 重放过程不依赖外部状态漂移（同一输入同一输出）

---

### 阶段 2：Evidence → EventWindow（核心语义压缩层）

目标：
- 把多源事件统一压缩为 Evidence，并构建可消费的 EventWindow（带冲突与标签）

交付物：
- Evidence Extractors（优先：liquidation/onchain/technical）
- Priority scoring 统一落地，且作为唯一排序来源
- Correlation/cluster 合成规则落地（用于把相关 evidences 聚合）
- ContextBuilder v1：TTL 过滤 + 冲突输出 + Top-K 压缩 + tags + cache

验收标准：
- EventWindow 输出规模受控：Top-K 生效，TTL 过期证据被清理
- 冲突可见：存在相互矛盾证据时，event window 必须输出 conflicts，不允许静默吞掉
- 结果稳定：同一 evidences 集合多次构建 event window 的输出一致（缓存不改变语义）

---

### 阶段 3：接入 Agent（EventWindow 驱动的世界模型与单决策链）

目标：
- MarketStateEngine 以 `selected_event + event_window` 为核心输入，结合 deterministic features 产出稳定 MSL；Decision Agent 只消费 msl + key_features + signal_event

交付物：
- agent_server_new 增加/替换 `EventWindowProvider`：从 Event Center 获取事件快照
- 上下文组装调整：active_events/recent_events 以 Event Center 输出为准，避免 agent 自行聚合
- DecisionTrace 记录点补齐：必须包含输入快照引用（context_id/时间窗/版本）与每步输出

验收标准：
- 任意一次决策可被“输入快照 + 决策链”复现：同一 event window 与 features 输入，输出 ExecutionPlan 稳定
- 预算可控：key_market_features 有硬上限，且不会因事件量增加而指数膨胀

---

### 阶段 4：Replay / Explain 产品化（可复盘、可回归）

目标：
- 建立事件与决策的重放工具链，支持对比与回归测试

交付物：
- `event_replay`：按时间窗读取 raw/normalized/evidence/context/selected，重放 stages，输出差异报告
- `decision_replay`：读取 DecisionTrace/输入快照，重放决策链，输出差异报告
- 回归样例集（golden fixtures）：覆盖至少 3 类事件组合（单源/多源/冲突）

当前进展：
- 已提供最小内存版 `event_replay` 工具骨架（`event_center_new/ec/pipeline/replay.py`），支持重放与 selected 差异比较

验收标准：
- 重放输出可对比：同一版本应 0 diff；不同版本 diff 可定位到某一阶段产物的字段变化
- LLM 参与时可复现：要么记录 LLM 输出作为输入快照的一部分，要么回放时使用 deterministic 替代（不允许“回放不可复现”）

---

## 6. 字段清理与归一规则（迁移指南）

原则：语义单一。以下为常见归一方向（保持不变）：

- 旧 `event_type`（有时是插件名） → 新 `type`（稳定语义命名空间），插件名放入 `payload.plugin` 或 `meta.plugin`
- 旧 `source`（包含实现名字符串） → 新 `source_name`（实现名） + `source_category`（协议语义）
- 旧 `payload.summary.primary_tf` → 新 `Evidence.horizon` 或 `meta.timeframe`（不要强制所有来源都有 tf）
- 旧 `event_level`/`priority` 混用 → 新：`importance`（先验）与 `priority`（阶段输出）分离

---

## 7. 风险点与防线（必须守住的底线）

- Evidence 引入 LLM 时必须强制输出结构化 Evidence，禁止原始文本直接进入下游
- Context Builder 必须做 Top-K 与 TTL，否则信息会指数膨胀并拖垮下游决策
- 冲突消解必须输出 conflicts，否则下游会在“看起来很强但互相打架”的状态下做错误决策
- 优先级排序必须统一由 Priority Engine 给出，否则不同模块各自排序会造成结果漂移
- `mixed` 方向不应被简单丢弃：允许输出但必须降权并携带冲突依据；仅噪声型 mixed 才可过滤

---

## 8. 参数配置与 AI 接管策略（新增）

目标：让复杂的 type 组合与权重配置可演进、可审计、可回放。

### 8.1 当前参数来源

- correlation 规则：`a_type + b_type -> out_type`
- priority 公式：`importance * strength * confidence * recency_decay`
- 关键配置：type 白名单、source/category 权重、half_life、路由阈值

### 8.2 AI 接管分阶段

1. 建议模式：AI 产出配置建议与影响评估，不直接生效
2. 审核发布：人工确认后版本化发布
3. 受限自动化：仅在允许区间自动调参，必须通过 replay 回归
4. 审计追踪：记录建议来源、配置 diff、生效版本、回放结果
