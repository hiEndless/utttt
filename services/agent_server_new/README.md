# agent_server_new

统一契约入口：`/docs/CONTRACT_INDEX.md`
项目级新架构总览：`/docs/ARCHITECTURE_NEW.md`
统一告警码清单（含 owner/introduced_in/lifecycle）：`/docs/ALERT_CODES.md`
本模块重构方案：`services/agent_server_new/docs/REFACTOR_PLAN_V2.md`
记忆层升级计划：`services/agent_server_new/docs/MEMORY_UPGRADE_PLAN.md`
记忆归档代办：`services/agent_server_new/docs/MEMORY_ARCHIVE_TODO.md`
AI 自适应预留：`services/agent_server_new/docs/AI_ADAPTIVE_RESERVE_PLAN.md`
runner JSON 输出契约：`services/agent_server_new/docs/runner_output_contract.md`

`agent_server_new` 是目标架构中的 **Decision Agent**，只负责决策层，不再承载长期稳定的状态生产职责，也不负责真实执行。

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

`agent_server_new` 只承担以下职责：

- consume `signal_event`
- consume `active_events`
- consume `MSL`
- 做 signal evaluation
- 做 intent resolve / rule planning
- 做 strategy gating / risk gating
- 产出 `ExecutionPlan`
- 产出 `DecisionTrace`

`agent_server_new` 不承担以下职责：

- 不采集原始市场数据
- 不计算指标和结构特征
- 不维护事件中心
- 不长期拥有 `MarketStateEngine`
- 不直接下单执行
- 不承担订单路由、成交回执对账、仓位对账

一句话定义：

> `agent_server_new` 只做“基于既有市场状态与事件上下文的决策”，不做“状态生成”，也不做“执行落地”。

## 目标输入输出

### 输入

来自两个上游：

1. `event_center_new`
   - `signal_event`
   - `active_events`（消费侧最小字段白名单：`event_id/source/type/asset/direction/score/timeframe/evidence`）
   - `active_events.evidence` 可携带 `trace` 摘要（如 `schema_version`）用于回放追溯
   - `active_events.evidence` 同步补充来源语义：`event_source/event_source_category/inference_source`
   - 外部事件（舆情/链上/新闻等）
2. `market_state_engine`
   - `MSL`（由结构事件与结构特征归纳后的状态）
   - `msl_meta`（schema/inference 元信息）
   - `msl_bundle`（short/mid/long 多周期状态）
   - `cross_horizon`（含 `suggested_policy/policy_reason`）
   - `key_features`
   - `anomaly_flags`
   - `state_features.evidence.alternative_sources`（news/social/onchain 标准化证据包，agent 侧汇总为 `alternative_source_summary`）
   - `alternative_source_summary.available_sources` 使用“有效可用”语义：`provider_state=noop/empty/unavailable/none` 且 `features` 为空时视为不可用
   - `alternative_source_summary` required keys：`available_sources/unavailable_sources/provider_states/data_sources/inference_sources/feature_keys/evidence_counts`
   - `alternative_source_summary.provider_states` 允许值（agent 汇总视角）：`primary/fallback/static/noop/unavailable/empty/ok/event_evidence_present`
   - 统一策略单源：`contracts/semantic_policies/source_semantics.yaml`（`alternative_sources_summary.provider_state_policy`）

仓位与账户上下文（`position_context`）由 `execution_service` 侧读取并裁决，不再作为 agent 裁决输入。

冻结流向约定：

- 结构事件先经 `market_state_engine` 归纳为 `MSL` 再进入决策层。
- 舆情/链上/新闻等外部事件由 `event_center_new` 直接进入决策层。
- 决策层按结构状态白名单消费 `MSL`，不依赖 `sentiment_state` 等已下线字段。
- 决策层可直接消费 `cross_horizon.suggested_policy` 作为周期冲突处理参考，不自行重复拼接规则。
- `position_context` 下沉到 `execution_service` 做最终风险与仓位裁决，不再作为 agent 裁决输入。

### 输出

输出给 `execution_service`：

- `ExecutionPlan`

输出给观测与复盘系统：

- `DecisionTrace`

## 推荐决策链路

```text
signal_event + active_events + MSL
  -> SignalEvaluator
  -> IntentResolver
  -> RulePlanner
  -> HorizonPolicyGate（消费 `cross_horizon.suggested_policy`）
  -> StrategyGate
  -> RiskGate
  -> ExecutionPlanner
  -> ExecutionPlan
  -> DecisionTrace
```

补充：
- `TradeEventWorkflow.run()` 继续返回 `ExecutionPlan`（兼容）
- `TradeEventWorkflow.run_with_result()` 返回 `WorkflowResult(agent_plan, execution_result)`，用于消费 execution 最终动作

## 当前与目标链路

### 当前实现（过渡态）

- `SignalEvaluator -> IntentResolver -> RulePlanner -> HorizonPolicyGate -> StrategyGate -> RiskGate -> ExecutionPlanner`
- 说明：部分 `Rule/Risk/Execution` 逻辑仍在 agent 内，便于当前链路可运行。

### 目标收敛（冻结方向）

- `SignalEvaluator -> HorizonPolicyGate -> DirectionDecision`
- `execution_service` 接管仓位/账户/PnL 风控与最终动作裁决。
- `Position Context` 不再作为 agent 裁决输入。

其中：

- LLM 只负责语义判断、解释、冲突权衡
- 硬约束必须在确定性 gate 中生效
- `ExecutionPlan` 是决策层终点，不是执行层入口代码
- `HorizonPolicyGate` 在策略门控前执行，用于把跨周期冲突建议快速转为保守动作（例如 `wait_confirmation -> skip/watch`）
- `HorizonPolicyGate` 已抽离为独立领域模块：`services/agent_server_new/domain/horizon_policy_gate.py`
- 账户/仓位/PnL 相关信息由 execution 层读取并做最终动作裁决，agent 不承担该部分权责
- `HorizonPolicyGate` 规则已配置化：
  - `block_on_increase_policies`（默认：`wait_confirmation,reduce_risk`）
  - 可通过 `TradeEventWorkflow(horizon_policy_config=...)` 注入覆盖
  - 也可通过环境变量统一加载：
    - `AGENT_HORIZON_POLICY_BLOCK_ON_INCREASE`（CSV）
    - `AGENT_HORIZON_POLICY_CONFIG_JSON`（JSON，支持完整配置覆盖）
  - 推荐使用样例文件：`services/agent_server_new/.env.example`

## 运行配置（建议）

- `AGENT_RUNTIME_PROFILE`
  - 运行档位（`dev|prod`，默认：`dev`）
  - `prod` 下门禁：要求 `AGENT_ACTIVE_EVENTS_PROVIDER_MODE=redis`，且 Redis provider 初始化失败时不允许回落
- `AGENT_MARKET_STATE_BASE_URL`
  - `market_state_engine` 服务地址（默认：`http://127.0.0.1:8300`）
- `AGENT_MARKET_STATE_TIMEOUT_S`
  - market_state HTTP 请求超时秒数（默认：`10`）
- `AGENT_EXECUTION_ENABLED`
  - 是否启用 execution_service 下游裁决（默认：`false`）
- `AGENT_EXECUTION_BASE_URL`
  - execution_service 服务地址（默认：`http://127.0.0.1:9962`）
- `AGENT_EXECUTION_TIMEOUT_S`
  - execution_service HTTP 请求超时秒数（默认：`10`）
- `AGENT_EXECUTION_RETRY_MAX`
  - execution_service HTTP 请求最大重试次数（默认：`0`，即不重试）
- `AGENT_EXECUTION_RETRY_BACKOFF_S`
  - execution_service HTTP 重试基础退避秒数（默认：`0.2`，按指数退避）
- `AGENT_EXECUTION_RETRY_ON_STATUSES`
  - 触发重试的 HTTP 状态码列表（CSV，默认：`429,500,502,503,504`）
- `AGENT_LLM_ENABLED`
  - 是否启用 LLM 运行时配置门禁（默认：`false`；当前仍不接管主决策链路）
- `AGENT_LLM_PROVIDER`
  - LLM provider 标识（默认：`openai_compatible`）
- `AGENT_LLM_MODEL_ID`
  - LLM 模型 ID（当 `AGENT_LLM_ENABLED=true` 且生产环境时必填）
- `AGENT_LLM_BASE_URL`
  - LLM 兼容接口地址（可选）
- `AGENT_LLM_API_KEY`
  - LLM API Key（当 `AGENT_LLM_ENABLED=true` 且生产环境时必填）
- `AGENT_LLM_API_KEY_ENV`
  - API Key 环境变量名（可选；当未设置 `AGENT_LLM_API_KEY` 时从该变量读取）
- `AGENT_LLM_TIMEOUT_S`
  - LLM 旁路观察请求超时秒数（默认：`8`）
- `AGENT_LLM_RETRY_MAX`
  - LLM 旁路观察最大重试次数（默认：`1`）
- `AGENT_LLM_RETRY_BACKOFF_S`
  - LLM 旁路观察重试基础退避秒数（默认：`0.2`，按指数退避）
- `AGENT_POSITION_CONTEXT_PROVIDER_MODE`
  - 仓位上下文 provider 模式（仅支持 `http`）
- `AGENT_POSITION_CONTEXT_BASE_URL`
  - 当 provider 为 `http` 时读取 execution debug state 的服务地址（默认回落 `AGENT_EXECUTION_BASE_URL`）
- `AGENT_POSITION_CONTEXT_TIMEOUT_S`
  - 仓位上下文 HTTP 请求超时秒数（默认回落 `AGENT_EXECUTION_TIMEOUT_S`）
- `AGENT_POSITION_CONTEXT_ACCOUNT_ID`
  - 读取仓位上下文时使用的账户 ID（默认：`main`）
- `AGENT_POSITION_CONTEXT_REDACT`
  - 是否请求脱敏 debug state（默认：`true`）
- `AGENT_POSITION_CONTEXT_FAIL_OPEN`
  - HTTP 获取失败是否回落空上下文（dev 默认 `true`，prod 默认 `false`）
- `AGENT_ACTIVE_EVENTS_PROVIDER_MODE`
  - active events provider 模式（仅支持 `redis`，默认：`redis`）
- `AGENT_ACTIVE_EVENTS_ALLOW_NULL_FALLBACK`
  - 非生产环境是否允许 Redis 初始化失败回落到 `null provider`（默认：`false`）
- `AGENT_ACTIVE_EVENTS_REDIS_URL`
  - 当 provider 为 `redis` 时的连接地址（默认：`redis://127.0.0.1:6379/0`）
- `AGENT_ACTIVE_EVENTS_STREAM`
  - active events Redis stream 键（默认：`ec:selected`）
- `AGENT_ACTIVE_EVENTS_LIMIT_DEFAULT`
  - 每次读取 active events 的目标条数（默认：`20`）
- `AGENT_ACTIVE_EVENTS_SCAN_FACTOR`
  - stream 扫描倍率（默认：`5`，实际扫描条数约为 `limit * factor`）
- `AGENT_EVENT_RECORDER_MODE`
  - 决策记录器模式（`none|jsonl`，默认：`none`）
- `AGENT_EVENT_RECORDER_JSONL_PATH`
  - 当记录器模式为 `jsonl` 时的输出路径（默认：`verification/reports/agent_server_new_events.jsonl`）
- `AGENT_EVENT_RECORDER_ROTATE_DAILY`
  - JSONL 是否按 UTC 日期滚动（默认：`true`）
- `AGENT_EVENT_RECORDER_MAX_BYTES`
  - 单文件最大字节数（默认：`10485760`，即 10MB；超过后追加 `.1/.2...` 分片）
- `AGENT_SYMBOL_MEMORY_ENABLED`
  - 是否启用 symbol 级记忆注入（默认：`false`）
- `AGENT_SYMBOL_MEMORY_BACKEND`
  - 记忆后端（`inmemory|redis`，默认：`inmemory`）
- `AGENT_SYMBOL_MEMORY_REDIS_URL`
  - 当后端为 `redis` 时的连接地址（默认：`redis://127.0.0.1:6379/0`）
- `AGENT_SYMBOL_MEMORY_INDEX_KEY`
  - Redis 维护 symbol 列表的索引键（默认：`agent:memory:symbols:index`）
- `AGENT_SYMBOL_MEMORY_CONTEXT_TOPK`
  - 注入到决策上下文的 recent memory 条数（默认：`5`）
- `AGENT_SYMBOL_MEMORY_CONTEXT_TTL_MS`
  - recent memory 注入的时间窗口（毫秒，默认：`86400000`）
- `AGENT_SYMBOL_MEMORY_CONTEXT_DEDUP_KEY`
  - recent memory 去重键（默认：`event_id`）
- `AGENT_AI_ADAPTIVE_ENABLED`
  - 是否启用 AI 自适应策略预留字段输出（默认：`false`）
- `AGENT_AI_ADAPTIVE_MODE`
  - 预留模式（`observe|recommend|bounded_apply`，默认：`observe`）
- `AGENT_HORIZON_POLICY_BLOCK_ON_INCREASE`
  - HorizonPolicyGate 阻断策略列表（CSV）
- `AGENT_HORIZON_POLICY_CONFIG_JSON`
  - HorizonPolicyGate JSON 配置（用于覆盖默认规则）

可直接参考：`services/agent_server_new/.env.example`

## Bootstrap

- 提供默认工厂：`agent_server_new.app.create_trade_event_workflow_from_env`
- 默认接线：
  - `market_state = HttpMarketStateProvider.from_env()`
  - `position_context` 使用 `http` 读取 execution debug state
  - `active_events` 默认 `RedisActiveEventsProvider`（默认初始化失败直接抛错；仅非生产且 `AGENT_ACTIVE_EVENTS_ALLOW_NULL_FALLBACK=true` 时回退 null provider）
  - Redis provider 会把 `selected_event` 归一成 `active_events` 最小结构：`event_id/source/type/asset/direction/score/timeframe/evidence`
  - `execution_decider = HttpExecutionDecisionProvider.from_env()`（当 `AGENT_EXECUTION_ENABLED=true`）
  - `event_recorder = JsonlEventRecorder.from_env()`（当 `AGENT_EVENT_RECORDER_MODE=jsonl`）

### MarketState 语义告警（非阻断）

`HttpMarketStateProvider` 会在读取状态层快照时追加语义告警到 `anomaly_flags`，用于提前发现字段语义漂移，不阻断策略执行：

- `state_features_semantic_contract_missing`
- `state_features_confidence_*`（周期 confidence 主从字段锚点不一致）
- `state_features_risk_*`（`risk_flags` / `risk_metrics` 边界不一致）
- `state_features_market_state_*` / `state_features_risk_bias_*`（歧义字段污染）
- `state_features_*_alias_applied`（消费侧已将歧义别名自动收敛到 canonical 字段，便于平滑迁移）

消费侧 canonical 收敛规则（`state_features`）：
- `market_state -> source_market_state`
- `risk_bias -> action_risk_bias`
- `horizons.{hz}.horizon_confidence -> horizons.{hz}.confidence`（缺失 canonical 时回填）

## CLI Smoke Test

- 最小运行入口：`python -m services.agent_server_new.main --dry-run`
- 单次执行示例：
  - `python -m services.agent_server_new.main --exchange binance --symbol ETHUSDT --signal-direction long --payload-json '{"event_type":"manual_signal"}'`
  - `python -m services.agent_server_new.main --exchange binance --symbol ETHUSDT --signal-direction long --use-execution-result`
  - `python -m services.agent_server_new.main --exchange binance --symbol ETHUSDT --signal-direction long --use-execution-result --print-json`
  - `python -m services.agent_server_new.main --exchange binance --symbol ETHUSDT --signal-direction long --use-execution-result --fail-on-execution-reject`

## HTTP Runtime (Production Probe)

- 启动 HTTP 入口：`python -m services.agent_server_new.runtime.http_main`
- 健康检查：`GET /internal/agent/healthz`
- 版本信息：`GET /internal/agent/version`（`contract_version/runtime_version/runtime_profile`）
- 就绪检查：`GET /internal/agent/readyz`
  - 当 workflow bootstrap 失败时返回 `503`
  - 响应包含 `status_level`：`green`（无告警）/`yellow`（仅 warning）/`red`（存在 error）
  - `prod` 档位且 `AGENT_EXECUTION_ENABLED=false` 时输出 warning：`execution_decider_disabled_in_production`
  - 可选上游检查（默认开启 market_state / redis）：
    - `AGENT_READY_CHECK_MARKET_STATE=true|false`
    - `AGENT_READY_CHECK_EXECUTION_SERVICE=true|false`（仅 `AGENT_EXECUTION_ENABLED=true` 时执行，默认跳过）
    - `AGENT_READY_CHECK_ACTIVE_EVENTS_REDIS=true|false`
    - `AGENT_READY_CHECK_EVENT_RECORDER=true|false`
    - `AGENT_READY_CHECK_EVENT_RECORDER_MIN_FREE_BYTES=104857600`
    - `AGENT_READY_CHECK_TIMEOUT_S=1.5`
    - `AGENT_READY_CHECK_UPSTREAM_STRICT=true|false`（`false` 时记 warning，不阻断 ready；`true` 时转为 error 并返回 `503`）

## Memory Summary Runner

- 一次执行：`python -m services.agent_server_new.memory_summary_runner --limit-symbols 500 --summary-window 50`
- 循环执行：`python -m services.agent_server_new.memory_summary_runner --loop --interval-s 60`
- 结果落盘：`python -m services.agent_server_new.memory_summary_runner --output verification/reports/memory_summary.latest.json`
- 本地快捷脚本：`bash tools/local/run_agent_memory_summary_report.sh`
- summary 现包含契约告警聚合：`contract_warning_count`、`contract_warning_event_count`、`contract_warning_type_count`、`recent_contract_warning_types`
- runner 支持 `--top-risk-n`，输出按 `contract_warning_count` 排序的 `high_risk_symbols`（观测用途）
- 默认仅输出有告警 symbol；可用 `--risk-warning-min` 提高阈值，或用 `--include-no-warning` 包含 0 告警 symbol
- `high_risk_symbols` 新增 `risk_score`（`warning_count * recency_weight`）用于更稳定排序

## Recorder Tail

- 本地追踪最新决策日志：`bash tools/local/tail_agent_events.sh`
- 指定路径：`bash tools/local/tail_agent_events.sh verification/reports/agent_server_new_events.jsonl`
- 按字段过滤：`bash tools/local/tail_agent_events.sh --event-id evt-001 --record-type agent_output --agent-name decision_trace`
- 按关键字过滤：`bash tools/local/tail_agent_events.sh --contains execution_service_unreachable`
- 按 jq 过滤：`bash tools/local/tail_agent_events.sh --jq '.agent_name == "decision_trace"'`
- 友好展示（缩进 JSON）：`bash tools/local/tail_agent_events.sh --pretty`

## Memory Observability

`DecisionTrace` 已包含 `memory_metrics`：
- `memory_hit`
- `memory_raw_recent_count`
- `memory_filtered_recent_count`
- `memory_dropped_count`
- `memory_summary_field_count`
- `memory_summary_event_count`
- `contract_warnings`（来自 `market_state.anomaly_flags` 的契约/语义告警子集，当前收敛 `state_features_*`、`msl_*`，并追加 `alternative_sources_conflict_detected`、`alternative_sources_provider_state_invalid`）
- `alert_codes`（由 `contract_warnings` 映射出的标准告警码，如 `AGENT_ALTERNATIVE_SOURCES_CONFLICT`、`AGENT_ALTERNATIVE_SOURCES_PROVIDER_STATE_INVALID`）

## One-shot Pipeline Smoke

- 单进程串联 `market_state_engine -> agent_server_new`：
  - `python -m services.agent_server_new.pipeline_smoke --dry-run`
  - `python -m services.agent_server_new.pipeline_smoke --exchange binance --symbol ETHUSDT --signal-direction long`
  - `python -m services.agent_server_new.pipeline_smoke --exchange binance --symbol ETHUSDT --signal-direction long --use-execution-result`

## Contract Guards

- `verification/auditors/agent_server_new/test_active_events_contract_guard.py`
  - 守卫 `selected_event -> active_events` 最小字段依赖面
- `verification/auditors/agent_server_new/test_pipeline_traceability_contract.py`
  - 守卫 `event_center_new -> market_state_engine -> agent_server_new` 链路的可追溯性（signal source + evidence 摘要）

## 必须从 `agent_server_new` 中剥离的能力

如果严格对齐目标架构，以下能力不应继续长期放在 `agent_server_new` 内部：

- `market_state_engine`
- `MSL` 生产逻辑
- 基于 raw structure 的 anomaly synthesis
- 状态层 feature aggregation
- 长周期状态快照存储

这些都应收敛到未来独立的 `market_state_engine`。

## 推荐边界

### 应该保留在 `agent_server_new` 的能力

- decision workflow orchestration
- expert prompt building
- structured expert outputs
- intent resolution
- rule planning
- strategy gating
- risk gating
- execution planning
- decision trace / explainability

### 不应该保留在 `agent_server_new` 的能力

- raw market structure parsing
- feature aggregation
- event normalization
- event dedup / correlation
- exchange order execution
- reconciliation / fill tracking

## 目录建议

推荐收敛后的目录：

```text
agent_server_new/
  README.md
  app/
    workflows/
      trade_event_workflow.py
  domain/
    contracts.py             # SignalVerdict / Intent / RulePlan / ExecutionPlan / DecisionTrace contract refs
    intent_resolver.py
    rule_planner.py
    strategy_gate.py
    risk_gate.py
    execution_planner.py
  experts/
    base/
    signal_evaluator.py
  ports/
    event_input.py
    market_state.py
    position.py
    execution_plan_sink.py
    trace_sink.py
  adapters/
    event_center_adapter.py
    market_state_adapter.py
    position_context_adapter.py
  observability/
    decision_trace.py
```

说明：

- `domain/market_state_engine.py` 不应长期保留在这里
- `compat/market_structure.py` 只允许作为过渡兼容层
- `ports` 只描述输入输出，不描述 Redis/HTTP 细节

## 需要搬走的文件与能力

以下文件建议迁到未来的 `market_state_engine` 服务：

- `domain/market_state_engine.py`
- `domain/msl.py`

以下能力建议改造成状态层输入适配器，随后迁移到独立状态层服务：

- raw structure provider
- market state provider adapter

原因：

- 它们的核心职责是从 `market_structure/raw features` 生成状态摘要
- 这属于状态层，不属于决策层

以下文件应继续保留在 `agent_server_new`：

- `domain/intent_resolver.py`
- `domain/rule_planner.py`
- `domain/strategy_gate.py`
- `domain/risk_gate.py`
- `domain/execution_planner.py`
- `experts/signal_evaluator.py`
- `observability/decision_trace.py`
- `app/workflows/trade_event_workflow.py`

## 建议改名的 contract

为了让层次更清晰，建议把 contract 按服务边界区分。

### 属于 `market_state_engine`

- `MarketStateMSL`
- `MarketStateFeatures`
- `AnomalyFlags`
- `KeyMarketFeatures`

### 属于 `agent_server_new`

- `SignalVerdict`
- `IntentDecision`
- `RulePlan`
- `ExecutionPlan`
- `DecisionTrace`

如果当前 `domain/contracts.py` 同时放了状态层与决策层对象，建议拆分。

建议拆成：

- `services/market_state_engine/src/contracts.py`
- `services/agent_server_new/domain/contracts.py`

## 必须切断的依赖

`agent_server_new` 必须遵守以下依赖规则：

- 可以依赖：
  - `event_center_new` 发布的事件协议
  - `market_state_engine` 发布的状态协议
  - 与 execution 层约定的决策输出契约
- 不可以依赖：
  - `data_server` 的原始结构输出
  - `feature_service` 的内部存储结构
  - `execution_service` 的交易所 SDK 细节

严格规则：

> `agent_server_new` 不允许直接消费 raw structure 来生成最终 MSL。

否则状态层与决策层边界会再次塌陷。

## 需要调整的工作流

当前 `app/workflows/trade_event_workflow.py` 的总体方向是对的，但还需要继续收窄：

当前工作流里仍然通过 `ContextBuilder` 间接吸收市场状态构建逻辑，这只是过渡方案。

最终应改为：

1. 从 `event_center_new` 读入：
   - `signal_event`
   - `active_events`
2. 从 `market_state_engine` 读入：
   - `MSL`
   - `key_features`
   - `anomaly_flags`
3. 决策层只做决策，不做状态拼装与仓位风控裁决

也就是说：

- `ContextBuilder` 最终只应做轻量 assemble
- 不应继续承担 market state build

## 与 `execution_service` 的接口约定

`agent_server_new` 对执行层只输出标准计划，不输出执行细节。

建议固定为：

- `ExecutionPlan`
  - action
  - direction
  - sizing
  - allowance
  - confidence
  - notes
  - trace_ref

执行层负责：

- plan validation
- order routing
- exchange execution
- fill / reject handling
- reconciliation

决策层不应知道：

- 具体交易所 API 重试策略
- 下单幂等 token
- 成交回报状态机
- 仓位对账细节

## 迁移清单

### 第一阶段：逻辑剥离

1. 明确 `market_state_engine.py` 只是临时托管在本服务
2. 禁止新增任何 raw structure -> MSL 的新逻辑到决策层 workflow
3. 把 `domain/contracts.py` 中状态层对象和决策层对象分开

### 第二阶段：依赖反转

1. 新增 `ports/market_state.py`
2. 工作流通过 port 获取：
   - `MSL`
   - `key_features`
   - `anomaly_flags`
3. 删除 workflow 对兼容市场结构模块的直接依赖

### 第三阶段：物理拆分

1. 把 `domain/market_state_engine.py` 搬到新服务
2. 把 `domain/msl.py` 搬到新服务
3. 把 raw structure / market state adapter 下沉到独立状态层服务
4. `agent_server_new` 只保留 `market_state` port 和 adapter client

## 当前版本相对目标架构的问题

当前版本最大的偏差有三个：

1. `MarketStateEngine` 仍在 `agent_server_new` 内
2. 部分状态层 contract 仍和决策层 contract 混在一起
3. workflow 还承担了部分状态组装责任

这些都不是方向错误，但说明当前仍处于“状态层和决策层半分离”的阶段。

## 收敛后的定义

`agent_server_new` 最终应该成为：

> 一个纯决策服务，消费事件层和状态层的标准输入，输出稳定的 `ExecutionPlan` 与 `DecisionTrace`，而不是继续兼任市场状态生产器或执行引擎。
