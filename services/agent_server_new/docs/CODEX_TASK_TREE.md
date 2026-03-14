# Codex 重构任务树（全局总控）

本文是为 codex cli 准备的“全局任务树 + 执行纪律”。目标是在不牺牲可验收性的前提下，让 codex 可以持续拆解、持续交付，并且每一步都能回滚。

覆盖模块：
- `feature_service/`
- `market_state_engine/`
- `agent_server_new/`
- `event_center_new/`

---

## 0. 全局执行纪律（必须遵守）

### 0.1 一次只做一个“闭环任务包”

- 每次只执行 1 个 run 文档（例如 `CODEX_RUN_001.md`）。
- 不允许在同一次 run 内跨多个服务随意改接口；如果确实需要跨服务改动，必须在 run 文档里写清楚“契约变更与向后兼容策略”。

### 0.2 每个任务必须包含 4 件事

1) 范围（只允许修改哪些文件）
2) 契约（必须保持哪些对外字段/路径/数据结构）
3) 验收（至少 1 条可运行自检：import/py_compile/单测/fixture diff/healthz）
4) 回滚（失败时恢复到什么行为：stub/null provider/fallback）

### 0.3 不可突破的红线

- 不允许为了“先跑起来”而把 schema 校验吞掉（除非明确记录为临时降级，并写清删除条件）。
- 不允许把原始新闻/社媒文本直接注入 Context/Decision 输入；LLM 若参与，只允许输出结构化 Evidence。
- 不允许默认依赖旧 `agent_server/`，也不允许新增 compat/fallback 回退壳。
- 不允许在一次 run 里做“大改目录 + 大改契约 + 大改业务逻辑”三件事同时发生。

---

## 1. 目标形态（按生产级蓝图对齐）

端到端链路（Feature Layer 之后）：

`feature_service` → `market_state_engine` → `agent_server_new`

并在未来把 `event_center_new` 插入为“事件中台”，为状态层与决策层提供事件上下文：

`event_center_new` →（MarketContext / active evidences）→ `market_state_engine` & `agent_server_new`

---

## 2. 依赖关系图（谁先做、谁后做）

P0（必须先解决：保证能跑、能测、能持续迭代）：
- agent_server_new：导入/目录一致性、ports 完整性、最小 workflow 可实例化
- feature_service：对外响应 schema 与 contracts 对齐；默认启动不依赖旧 agent_server（如你已有 TASKS.md，可按其推进）

P1（稳定性与可回归资产）：
- market_state_engine：对 raw_structure schema 的显式校验与降级；golden fixtures

P2（事件闭环与生产级关键能力）：
- event_center_new：runtime + storage + replay 的最小闭环，提供 internal API 供 agent 读取 active events/context

---

## 3. 任务树（T00–T15）

说明：任务编号用于 run 文档引用；run 文档必须列出“本次要完成的任务编号”。

### T00 统一最小可运行基线（四服务 smoke）
- 输出：每个服务至少具备 import + app 创建 + healthz（或等价自检）

### T01 修复 agent_server_new 的 ports 路径一致性（确保 workflow 可导入）
- 重点：补齐/修正 `ActiveEventsProvider`、`PositionContextProvider` 等 ports 定义与引用路径

### T02 统一 feature_service 对外响应 schema（修 contracts 漂移）
- 重点：`/features` 返回结构与 `FeatureSnapshot` 对齐（或契约显式升级且向后兼容）

### T03 引入 schema_version 并贯穿 feature → state → agent
- 重点：feature_service 与 market_state_engine 输出带 `schema_version`；下游显式校验/降级

### T04 切断 feature_service 对旧 agent_server 的默认运行期依赖
- 重点：默认 wiring 不导入旧 agent_server，也不保留 compat/fallback 回退路径

### T05 为 feature_service 增加 null/noop providers 与独立组装模式
- 重点：无外部依赖也能启动并返回结构完整的“空数据”

### T06 market_state_engine 显式声明 raw_structure 关键字段依赖与缺失降级
- 重点：缺字段时 anomaly_flags 明确可解释，避免静默 unknown

### T07 market_state_engine 建立 golden fixtures（raw_structure → MSL）
- 重点：至少 3 组输入（正常/缺字段/极端），输出关键字段断言

### T08 agent_server_new 建立最小集成测试（state snapshot → execution plan）
- 重点：固定输入，断言 `ExecutionPlan` 与 `DecisionTrace` 的关键字段稳定

### T09 event_center_new 落地最小运行时（in-memory runtime v1）
- 重点：ingest → normalize → raw/normalized 存储；dedup 基础

### T10 event_center_new 实现 1 个 EvidenceExtractor（liquidation/onchain 二选一）
- 重点：deterministic evidence 输出 + fixture

### T11 event_center_new 实现 ContextBuilder v1（Top-K + TTL + conflicts）
- 重点：输出规模受控、冲突可见、结果稳定

### T12 event_center_new 提供 internal API（ingest + query active/context）
- 重点：让 agent_server_new 能从 event_center_new 读取 active events/context

### T13 agent_server_new 替换 active_events_stub 为 event_center_http provider
- 重点：active_events 真正来自事件中心；初始化失败直接报错，不保留 stub/null fallback

### T14 决策可回放闭环：DecisionTrace recorder v1
- 重点：可按 event_id 查询 trace；同输入重放输出稳定

### T15 event_replay + decision_replay（diff 输出）
- 重点：同版本 0 diff；不同版本 diff 可定位阶段与字段

---

## 4. 文档组织建议（给 codex 的入口）

- 全局总控：本文件 `CODEX_TASK_TREE.md`
- 执行包：按编号创建 `CODEX_RUN_XXX.md`（每次只投喂一个 run）
- 若某个服务已存在 `TASKS.md`（例如 `services/feature_service/TASKS.md`），run 完成后同步更新勾选状态，并在 run 文档末尾写“完成摘要 + 验收结果”。
