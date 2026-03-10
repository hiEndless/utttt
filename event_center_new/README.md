# event_center_new

项目级新架构总览：`/docs/ARCHITECTURE_NEW.md`
运行时配置总表：`event_center_new/docs/runtime.md`
运行时配置版本号与变更日志也在该文档中维护（`runtime_config_version`）。
版本升级可使用：`bash scripts/bump_event_center_runtime_version.sh <version> <note>`（支持 `--dry-run` 预览、`--check-clean` 干净工作区保护、`--apply-from-env-table` 环境变量覆盖校验、`--no-duplicate-log` 防重复日志、`--strict` 一键严格模式）。当前版本可用 `--print-current-version` 只读查询。

`event_center_new` 是目标架构中的 **Event Center**，只负责事件层，不负责市场状态归纳，不负责交易决策，不负责执行。

目标收敛架构：

```text
data_server
  -> feature_service
    -> event_center_new
      -> market_state_engine
        -> agent_server_new
          -> execution_service
```

## 在总架构中的职责

`event_center_new` 只承担以下职责：

- ingest：接入多源事件输入（exchange / onchain / news / social / liquidation / strategy signal）
- normalize：把不同来源统一成稳定的事件契约
- dedup：做去重、幂等、trace 传递
- correlate：把同一时间窗、同一资产、同一主题的事件建立关联
- classify：做事件类型、事件层级、时间跨度、触发性质分类
- prioritize：做事件重要性和路由优先级排序

`event_center_new` 不承担以下职责：

- 不生成 MSL
- 不输出市场 regime / structure summary
- 不做 strategy planning / risk gating
- 不输出 `ExecutionPlan`
- 不直接依赖 `agent_server_new` 的领域契约

一句话定义：

> Event Center 的输出应该是“经过清洗、归一、关联、排序后的事件与证据”，而不是“市场结论”或“交易结论”。

## 输入与输出

### 输入

来自上游两类来源：

- `data_server`：原始事件流
  - exchanges
  - onchain
  - news
  - social
- `feature_service`：特征派生结果中产生的事件型输出
  - indicator crosses
  - volatility burst
  - open interest jump
  - liquidation cluster
  - structure break / reclaim

### 输出

输出给两个下游：

1. `market_state_engine`
   - 仅消费“结构相关事件”（如指标/波动/OI/流动性/结构破位）
2. `agent_server_new`
   - 消费全部决策事件输入
   - 包含“外部事件”（舆情/链上/新闻等）与结构事件

冻结流向约定：

- 结构事件：`event_center_new -> market_state_engine -> agent_server_new`
- 外部事件（舆情/链上/新闻）：`event_center_new -> agent_server_new`

建议输出拆成两类：

- `SelectedEvent`
  - 适合进入状态层或决策层的标准事件
- `EventBatch`
  - 某个资产某个时间窗内的活跃事件集合，包含去重和优先级结果

## 推荐边界

### 应该保留在 `event_center_new` 的能力

- source adapters
- event normalization
- evidence extraction
- ttl / decay
- dedup / idempotency
- correlation / clustering
- classification / tagging
- prioritization / routing hints
- event memory（短期事件记忆）

### 不应该留在 `event_center_new` 的能力

- market regime inference
- MSL generation
- trade intent / execution planning
- execution risk gating

如果某个处理步骤开始回答“现在市场是什么状态”，它就已经不属于 `event_center_new`。

## 推荐契约

建议把当前契约收敛为纯事件中心语义。

### 保留

- `EventEnvelope`
- `Evidence`
- `EventContextSnapshot`
- `ClassifiedEvent`
- `PrioritizedEvent`
- `SelectedEvent`
- `EventTrace`

## 目录建议

推荐收敛后的目录：

```text
event_center_new/
  README.md
  docs/
    schema.md
    refactor.md
  ec/
    contracts.py              # EventEnvelope / Evidence / ClassifiedEvent / PrioritizedEvent / SelectedEvent
    pipeline/
      stages.py
    sources/
      base.py
      exchange/
      onchain/
      news/
      social/
    storage/
      memory.py
```

说明：

- `event_center_new` 当前以协议与可组合模块为主（contracts + protocols + in-memory 组件）
- 已提供最小运行时 `EventPipelineRunner` 与 `event_center_new/main.py` 示例入口（内存 source/store）
- 已提供 Redis 分层写入适配器（`ec/storage/redis.py`），支持写入 `ec:raw/ec:normalized/ec:evidence/ec:context/ec:selected`
- 当前仅维护 memory/redis 存储适配器，其他适配器暂不纳入近期计划
- 已提供最小 `event_replay` 工具（`ec/pipeline/replay.py`），可按输入事件重放并比较 selected 差异
- 对外语义以 `SelectedEvent/EventWindow` 为主，不做市场状态推理

## 必须切断的依赖

`event_center_new` 必须遵守以下依赖方向：

- 可以依赖：
  - `data_server` 的输出协议
  - `feature_service` 的输出协议
  - 自己的 `contracts / pipeline / storage`
- 不可以依赖：
  - `agent_server_new.domain.*`
  - `market_state_engine.domain.*`
  - `execution_service.*`

严格规则：

> `event_center_new` 只能向下游发布事件契约，不能 import 下游服务的领域对象。

## 迁移清单

### 第一阶段：切边界（已完成）

1. 契约收敛到事件语义：`EventEnvelope/Evidence/EventContextSnapshot/SelectedEvent`
2. 与 `agent_server_new` 的领域契约解耦（不 import 下游领域对象）
3. 流水线语义收敛：`classify/prioritize/select`，不产出 `MSL`

### 第二阶段：稳定输出（进行中）

1. 固定 `EventEnvelope` / `Evidence` / `SelectedEvent` schema
2. 在 `docs/schema.md` 中明确：
   - ingest schema
   - normalized schema
   - prioritized schema
   - selected schema
3. 对外只暴露这些 schema，不暴露内部阶段对象

当前已落地：
- `event_center_new/docs/selected_event.schema.json`

### 第三阶段：为状态层提供干净输入（进行中）

`event_center_new` 对 `market_state_engine` 输出建议固定为：

- `selected_event`
- `event_window`
- `correlated_evidences`
- `priority`
- `trace`

而不是：`market_state/regime/summary/msl`

## 信号生成模式（新架构）

新架构不再采用“策略插件直接产最终信号”的模式，而是采用“事件证据融合后选择信号”：

1. `SourceAdapter.poll` 拉取事件并封装 `EventEnvelope`
2. `normalize/dedup` 统一字段与追踪信息
3. `EvidenceExtractor` 从事件提炼证据 `Evidence`
4. `CorrelationEngine` 依据规则做关联合成（可抑制输入类型）
5. `PriorityScorer` 依据统一公式打分
6. `classify/prioritize/select` 产出 `SelectedEvent`
7. 同步输出 `event_window`（活跃证据与冲突摘要）

核心变化：

- 旧架构：信号更像“某个策略插件结果”
- 新架构：信号是“多源证据融合选择结果”

## 关联合成与优先级依据

### 关联合成依据

- 由 `CorrelationRule` 明确配置，不是黑盒
- 典型规则：`a_type + b_type -> out_type`
- 合成字段：`out_direction/out_horizon/strength/importance/confidence`
- 可选 `suppress_inputs` 控制是否压制原输入类型

### 优先级评分依据

统一公式（当前实现）：

`score = importance * strength * confidence * recency_decay`

- `importance`: 事件先验权重（0~1）
- `strength`: 证据强度（0~1）
- `confidence`: 证据置信度（默认下限 0.2）
- `recency_decay`: 时间衰减（默认半衰期 15 分钟）

## 下游下发与依据携带

`SelectedEvent` 下发时应同时携带可回放依据，避免“只给结论不给证据”：

- 来源信息：`source.name/source.category`
- 跟踪信息：`trace.dedup_key/correlation_id/parent_id/schema_version`
- 生成条件：命中规则 ID、输入证据摘要、冲突信息
- 周期信息：`horizon`、`ttl_ms`、窗口时间戳
- 引用链：`source_refs`（关联原始事件 ID）

这使得下游可直接完成：

- 入库
- 回放
- 差异对比
- 审计解释

## mixed 方向处理约定（新增）

`direction_hint=mixed` 不等于“无信号”，表示证据存在冲突且当前无法收敛为单边结论。

处理规则：

1. `mixed` 允许进入 `select` 输出，但必须降权
2. `mixed` 输出必须携带 `conflicts` 与关键证据摘要
3. `mixed` 默认路由到 `market_state_engine` 做进一步融合
4. 仅“噪声型 mixed”可丢弃（低强度、低重要性、证据数量不足）

推荐附加字段：

- `direction_hint`: `bullish|bearish|neutral|mixed`
- `review_required`: `true|false`（`mixed` 通常为 `true`）
- `drop_reason`: 丢弃时的结构化原因码

## 与其他服务的接口约定

### 对 `feature_service`

输入来自 `feature_service` 的应该是“事件化特征”，例如：

- `indicator_cross`
- `volatility_expansion`
- `funding_extreme`
- `open_interest_spike`
- `liquidity_gap_detected`

事件中心不负责重新计算 feature。

### 对 `market_state_engine`

事件中心给状态层的是：

- 多源事件
- 证据集合
- 关联关系
- 时间衰减后的活跃事件集合

状态层自己决定如何结合 feature 做 regime / anomaly / MSL。

### 对 `agent_server_new`

事件中心可以直接给决策层提供：

- `signal_event`
- `active_events`

但这些都必须是事件语义，而不是市场状态语义。

## 当前版本的主要问题

当前版本相对目标架构，主要问题是生产级运行能力尚未闭环：

1. 最小 `runner` 已有，但缺长期稳定运行编排（调度/容错/监控）
2. 缺生产级存储适配器（raw/normalized/evidence/context/selected 分层落盘）
3. 缺 replay 工具链（按时间窗重放并做差异比较）

## 收敛后的定义

`event_center_new` 最终应该成为：

> 一个独立的事件中台，负责把多源原始输入整理成可消费、可追踪、可排序的事件流，为 `market_state_engine` 和 `agent_server_new` 提供干净事件输入。

## AI 接管配置的规划

后续支持 AI 接管参数配置需求，但采用分阶段治理：

1. AI 只生成配置建议，不直接生效
2. 人工审核后发布（附带 diff 与影响评估）
3. 受限自动调参（有边界、有回放验收）
4. 全链路记录配置版本、建议来源与生效结果

## 最小运行方式

内存模式（默认）：

```bash
python3 -m event_center_new.main
```

Redis 分层写入模式：

```bash
EVENT_CENTER_LAYER_STORE_MODE=redis \
EVENT_CENTER_REDIS_URL=redis://127.0.0.1:6379/0 \
python3 -m event_center_new.main
```

循环运行模式（最小调度）：

```bash
EVENT_CENTER_RUN_LOOP=true \
EVENT_CENTER_RUN_INTERVAL_MS=1000 \
EVENT_CENTER_RUN_MAX_TICKS=0 \
EVENT_CENTER_STOP_ON_ERROR=false \
EVENT_CENTER_HEALTH_KEY=ec:runner:health \
python3 -m event_center_new.main
```

说明：

- `EVENT_CENTER_RUN_LOOP=true` 开启循环模式
- `EVENT_CENTER_RUN_INTERVAL_MS` 每轮间隔（毫秒）
- `EVENT_CENTER_RUN_MAX_TICKS` 最大轮次，`0` 表示不限（常驻）
- `EVENT_CENTER_STOP_ON_ERROR` 事件处理异常时是否立即退出（默认 `false`）
- `EVENT_CENTER_HEALTH_KEY` 运行健康快照写入 Redis 的 key（默认 `ec:runner:health`）

启动自检模式（只做初始化与健康上报）：

```bash
EVENT_CENTER_SELF_CHECK_ONLY=true \
EVENT_CENTER_HEALTH_KEY=ec:runner:health \
python3 -m event_center_new.main
```

- `EVENT_CENTER_SELF_CHECK_ONLY=true` 时不会执行事件处理循环，仅执行最小依赖路径并上报一次健康状态。

最小健康信号（`EventPipelineRunner.health_snapshot()`）：

- `heartbeat`: 轮询心跳计数（每次 `run_once` +1）
- `last_run_ms`: 最近一次运行时间戳（毫秒）
- `run_count`: 累计运行轮次
- `error_count`: 累计事件处理异常数
- `last_error`: 最近一次异常摘要

当启用 Redis layer store 时，每轮还会把健康快照写入 `EVENT_CENTER_HEALTH_KEY`（JSON，含 `updated_ms`）。

最小回放用法（Python）：

```python
from event_center_new.ec.pipeline.replay import EventReplayTool, diff_selected
```

Redis 时间窗回放 CLI：

```bash
python3 -m event_center_new.replay_main \
  --redis-url redis://127.0.0.1:6379/0 \
  --start-ms 1773154000000 \
  --end-ms 1773154999999 \
  --ignore-field ts_ms \
  --ignore-field trigger_event.ts_ms \
  --strict \
  --summary-only \
  --output /tmp/event_replay_report.json
```

回放报告包含 `signatures.replay_selected` 与 `signatures.online_selected`，
可快速判断两轮 selected 是否一致，再结合 `diffs` 做字段级定位。
报告同时包含 `selected_contract`（顶层字段白名单/必填校验），可提前发现线上 selected 契约漂移。
`selected_contract` 校验规则直接复用 `event_center_new/docs/selected_event.schema.json`。
报告还包含 `stream_presence` 与 `missing_streams`，可用于 CI 在 `ec:raw/ec:selected` 缺失时快速失败。
`--strict` 等价于同时开启 `--fail-on-contract --fail-on-diff --fail-on-missing-stream`。
`--summary-only` 仅输出摘要字段，适合守卫/CI 场景降低日志噪音。
`--summary-only` 输出契约冻结为 `event_center_new/docs/replay_summary.schema.json`。
仓库守卫 `scripts/check_event_center_replay_guard.sh` 已包含该失败路径的行为断言，避免只检查参数存在。
仓库守卫 `scripts/check_event_center_replay_strict_ci.sh` 固定 `--strict --summary-only` 调用路径，覆盖严格模式成功/失败分支。
仓库守卫 `scripts/check_event_center_selected_schema_guard.sh` 也包含缺必填字段（如 `route`）的行为断言。
仓库守卫 `scripts/check_event_center_runtime_guard.sh` 覆盖 `stop_on_error` 与 `self_check_only` 的运行时分支。
仓库守卫 `scripts/check_event_center_runtime_doc_guard.sh` 校验 runtime 文档与 main.py 的环境变量集合强一致（双向）及版本日志一致性；可加 `--show-sets` 输出集合明细用于排障。
仓库守卫 `scripts/check_event_center_runtime_bump_tool_guard.sh` 校验 runtime 版本升级工具关键参数行为。
仓库守卫 `scripts/check_event_center_guard_wiring.sh` 校验 event_center 聚合守卫与顶层入口接线未失效；默认 `--strict`，可改 `--lenient` 过渡；可加 `--show-links` 输出接线引用行号。
仓库守卫 `scripts/check_event_center_ci_workflow_guard.sh` 校验 quick/full workflow 的失败诊断 artifact 与显式失败收敛步骤未丢失。
仓库守卫 `scripts/check_event_center_ci_doc_snapshot_guard.sh` 校验 `event_center_new/docs/ci.md` 的帮助快照与最短排障命令关键行未漂移（关键行来源：`event_center_new/docs/ci_help_snapshot_lines.txt` 与 `event_center_new/docs/ci_triage_snapshot_lines.txt`）。
仓库守卫 `scripts/check_event_center_help_snapshot_sync_guard.sh` 校验聚合守卫 `--help` 的完整输出块与失败码顺序强一致（快照：`ci_help_block_snapshot.txt`/`ci_help_snapshot_lines.txt`）。
`scripts/check_event_center_contract_guards.sh` 在子守卫失败时会统一输出 `FAIL_CODE=...`（schema/runtime/wiring/ci-workflow/ci-doc/help-snapshot-sync），便于日志检索与告警归类；可用 `--help` 查看失败码清单。
聚合入口：

- `scripts/check_event_center_contract_schema_guards.sh`（契约/Schema 相关）
- `scripts/check_event_center_runtime_family_guards.sh`（运行时相关）
- `scripts/check_event_center_contract_guards.sh`（总入口，组合调用上面两个聚合）

可通过聚合入口 `scripts/check_event_center_contract_guards.sh` 一次执行上述两类契约守卫。
该聚合守卫还会对 replay CLI 做参数快照校验（`--strict/--summary-only/--ignore-field/--output`）。
可用 `bash scripts/check_event_center_contract_guards.sh --quick` 执行快速模式（参数快照 + runtime 文档守卫 + bump tool 守卫 + 接线检查）。
接线检查策略可选：`--strict-wiring`（默认）或 `--lenient-wiring`。
全仓库守卫支持 event_center 快速模式：`bash scripts/check_new_arch_guards.sh --event-center-quick`（仅跑 event_center quick 子集）。
如需跑 event_center 全量子守卫，可用：`bash scripts/check_new_arch_guards.sh --event-center-only`。
顶层入口也支持接线策略透传：可追加 `--lenient-wiring`（默认 `--strict-wiring`）。
该 wiring 参数只影响 event_center 接线守卫，不改变其它模块守卫逻辑。

CI 便捷入口：

- `scripts/ci_event_center_quick_strict.sh`
- `scripts/ci_event_center_quick_lenient.sh`
- `scripts/ci_event_center_full_strict.sh`
- `scripts/ci_event_center_emit_meta_header.sh`（输出统一 CI 元信息头部：run_mode/git_sha/runtime_config_version/ts_utc）
- `.github/workflows/event-center-quick.yml`（GitHub Actions：并行执行 strict/lenient quick 守卫；失败自动上传 strict/lenient 诊断 artifact）
- `.github/workflows/event-center-full.yml`（GitHub Actions：每日定时 + 手动触发，全量 strict 守卫；失败自动上传诊断 artifact）
- `.github/actions/setup-utaker-python/action.yml`（quick/full 复用的 Python+依赖初始化 action）
- `event_center_new/docs/ci.md`（CI 触发矩阵、失败分类、artifact 日志锚点与标准处置）

CI 失败排障请直接查看 `event_center_new/docs/ci.md`，README 仅保留入口。
