# agent_server_new 数据流水线与字段契约（实现对齐版）

本文档面向 `/services/agent_server_new` 当前代码实现，按“真实执行顺序”梳理 agent 层（决策层）的数据链路：输入来自事件触发 + 状态层（MSL）+ 活动事件（active events）+（可选）symbol 记忆；输出为 agent 执行计划（ExecutionPlan），并可选调用 `execution_service` 做最终裁决，同时可写出可观测的 `DecisionTrace`。

主要依据：
- CLI 入口：[runner.py](services/agent_server_new/runtime/runner.py)
- 默认装配（ports -> adapters）：[bootstrap.py](services/agent_server_new/app/bootstrap.py)
- 工作流定义（主链路）：[trade_event_workflow.py](services/agent_server_new/app/workflows/trade_event_workflow.py)
- 上下文构建（输入聚合/裁剪）：[context_builder.py](services/agent_server_new/app/context_builder.py)
- 核心领域契约（枚举/字段）：[domain/contracts.py](services/agent_server_new/domain/contracts.py)
- 状态层输入端口与快照结构：[ports/market_state.py](services/agent_server_new/ports/market_state.py)
- 状态层 HTTP 适配器与契约守卫：[market_state_http.py](services/agent_server_new/adapters/market_state_http.py)
- active_events Redis 适配器与最小白名单：[active_events_redis.py](services/agent_server_new/adapters/active_events_redis.py)
- 可观测 trace 结构：[decision_trace.py](services/agent_server_new/observability/decision_trace.py)
- runner JSON 输出 schema：[runner_output.schema.json](services/agent_server_new/docs/runner_output.schema.json)

时间语义口径（canonical）：`docs/contracts/SEMANTIC_GLOSSARY.md`
- signal freshness 优先使用 `event_ts_ms`，并兼容 `ts_ms` 等历史字段
- active_events evidence 内建议保留 `event_ts_ms/processed_ts_ms`
- `ts_ms` 仅作为过渡兼容别名
- `intent/rule/strategy/risk/horizon/execution_planner` 历史模块已删除，旧链路术语仅用于迁移背景说明

---

## 0. 总览：端到端“真实执行顺序”

以 `TradeEventWorkflow.run_with_result()` 为准，主链路顺序：

1. 事件输入（TradeEventInput）进入 workflow
2. ContextBuilder 聚合输入：
   - market_state（MSL + cross_horizon + state_features + anomaly_flags + raw_market_structure）
   - position_context（来自 execution_service debug state）
   - active_events（从 event_center_new 的 selected_event 流归一化而来）
   - symbol_memory（可选，inmemory/redis）
3. signal_evaluator：输出 SignalVerdict（只裁决“信号有效性”，不直接决定动作）
4. signal_router：按事件类型路由到不同 signal decision agent
5. signal_decision_agent：输出语义判定（accept/reject/uncertain）与方向/置信度
6. workflow_decider：输出 ExecutionPlan（语义建议）
7. （可选）execution_decider：HTTP 调用 execution_service 返回最终裁决 dict
8. （可选）recorder：写出 market_context/agent_output/decision_trace
9. （可选）symbol_memory_recorder：写入本次决策摘要作为 symbol 记忆

主实现：[trade_event_workflow.py](services/agent_server_new/app/workflows/trade_event_workflow.py#L104-L369)

---

## 1. 模块形态与边界

### 1.1 形态

`agent_server_new` 当前是“库 + CLI runner”的形态：

- 有 CLI 入口：`python -m services.agent_server_new.main ...`
- **本模块内未提供 HTTP server 对外监听**（对外系统集成应由上层进程/任务调度调用）

入口实现：[runner.py](services/agent_server_new/runtime/runner.py)

### 1.2 职责边界（实现落点）

负责：
- 消费状态层 MSL（来自 `market_state_engine`）与关键证据（key_market_features）
- 消费活动事件（active_events）作为背景（默认来自 event_center_new 的 selected_event 流）
- 做信号初筛、意图解析、规则规划、门控与执行计划生成
- 可选把“意图/提示”提交给 execution_service 做最终执行裁决
- 可选写出决策 trace 与 symbol 记忆

不负责：
- 原始数据采集、特征计算（由 feature_service / market_state_engine 负责）
- 事件去重/分类/优先级（由 event_center_new 负责）
- 真实仓位/账户系统（通过 execution_service 提供的状态快照接入，最终执行裁决仍在 execution_service）

---

## 2. 入口：runner（命令行输入输出）

### 2.1 runner 输入参数

runner 通过 argparse 接收参数并构造 `TradeEventInput`：

| 参数 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| --event-id | string | manual-evt-001 | 事件 ID |
| --exchange | string | binance | 交易所 |
| --symbol | string | ETHUSDT | 交易对 |
| --signal-direction | string | long | 信号方向（long/short） |
| --payload-json | string(JSON) | {"event_type":"manual_signal"} | 事件 payload |
| --use-execution-result | bool | false | 优先输出 execution_service 最终动作 |
| --print-json | bool | false | JSON 输出，便于脚本消费 |
| --fail-on-execution-reject | bool | false | execution 返回 reject_reason 时退出码=2 |

实现：[runner.py](services/agent_server_new/runtime/runner.py#L12-L104)

### 2.2 runner 输出契约（JSON）

当 `--print-json` 时输出满足 schema 的 JSON：

- schema：[runner_output.schema.json](services/agent_server_new/docs/runner_output.schema.json)
- 文档说明：[runner_output_contract.md](services/agent_server_new/docs/runner_output_contract.md)

输出有两类 shape：

1) execution 可用：

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| source | const | Y | 固定 "execution" |
| action | string | Y | execution 的最终动作（不在本模块冻结枚举） |
| reason | string | Y | execution 的拒绝原因或说明（可为空字符串） |
| notes | string | Y | 备注（来自 agent_plan.notes 等） |

2) agent / agent_fallback：

| 字段 | 类型 | 必填 | 枚举 | 含义 |
|---|---|:---:|---|---|
| source | string | Y | agent / agent_fallback | 来源 |
| action | string | Y |  | agent 的计划动作（见 8.3 RiskAction） |
| direction | string | Y | long/short/none | 方向 |
| notes | string | Y |  | 说明 |

---

## 3. Ports / Adapters（边界与协议）

### 3.1 MarketStateProvider（状态层输入）

端口定义：
- `MarketStateProvider.get_market_state(exchange, symbol) -> MarketStateSnapshot`
- `MarketStateSnapshot` 字段见下（3.1.2）

定义：[ports/market_state.py](services/agent_server_new/ports/market_state.py#L9-L29)

#### 3.1.1 HTTP 适配器：HttpMarketStateProvider

调用：`GET {AGENT_MARKET_STATE_BASE_URL}/internal/market-state/{exchange}/{symbol}`  
默认 base_url：`http://127.0.0.1:8300`

实现：[market_state_http.py](services/agent_server_new/adapters/market_state_http.py#L56-L95)

#### 3.1.2 MarketStateSnapshot 字段表（agent 侧输入快照）

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| exchange | string | Y | 交易所 |
| symbol | string | Y | 交易对 |
| msl | MarketStateMSL | Y | 状态层 MSL（强枚举见 market_state_engine 文档） |
| msl_meta | object | Y | 推断元信息（schema_version/inference_version/...） |
| msl_bundle | object | Y | 多周期 MSL bundle（可为空） |
| msl_bundle_meta | object | Y | 多周期 meta（可为空） |
| cross_horizon | object | Y | 跨周期摘要（alignment/conflicts/suggested_policy/...） |
| state_features | object | Y | 状态层聚合特征（evidence/anomalies/horizons/...） |
| anomaly_flags | array[string] | Y | 状态层异常标签 + agent 的契约守卫标签（见 3.1.3） |
| raw_market_structure | object | Y | 审计用原始结构（上游 raw_market_structure） |

定义：[ports/market_state.py](services/agent_server_new/ports/market_state.py#L9-L23)

#### 3.1.3 状态层契约守卫（agent 侧附加 anomaly_flags）

HTTP 适配器会对 `msl` 与 `msl_meta.schema_version` 做最小契约检查，并把异常追加到 `anomaly_flags`：

| 追加标签 | 触发条件 |
|---|---|
| msl_contract_missing_required_fields | msl 缺少 required 字段集合 |
| msl_meta_schema_version_missing | msl_meta.schema_version 不存在/不可解析 |
| msl_meta_schema_version_unsupported | schema_version 不在 {1,2} |
| msl_version_schema_version_mismatch | msl.version 与 schema_version 不一致 |

实现：[market_state_http.py](services/agent_server_new/adapters/market_state_http.py#L11-L53)

### 3.2 ActiveEventsProvider（活动事件输入）

端口定义：`get_active_events(exchange, symbol) -> list[dict]`  
定义：[active_events_provider.py](services/agent_server_new/ports/data/active_events_provider.py#L6-L10)

#### 3.2.1 Redis 适配器：RedisActiveEventsProvider

从 Redis Stream 逆序扫描（默认 stream 为 `ec:selected`），将每条 selected_event 归一化为 agent 的 active_event 最小字段白名单。

实现：[active_events_redis.py](services/agent_server_new/adapters/active_events_redis.py#L12-L165)

#### 3.2.2 ActiveEvent（归一化后）字段表（agent 侧最小白名单）

`RedisActiveEventsProvider._normalize_active_event()` 会输出固定字段集合：

| 字段 | 类型 | 必填 | 枚举/范围 | 含义 |
|---|---|:---:|---|---|
| event_id | string | Y |  | 事件 ID（优先 payload.event_id/id，否则用 stream_id） |
| source | string | Y |  | 事件来源（默认 event_center_new） |
| type | string | Y |  | 事件类型（优先 selected_type/event_type/type） |
| asset | string | Y | exchange:symbol 或 symbol | 路由 key（用于匹配当前 symbol；缺失会回填） |
| direction | string | Y | bullish/bearish/neutral/mixed | 方向提示（非法值回退 neutral） |
| score | number | Y | 0~1（约定） | 优先级/强度分数（优先 payload.score，否则由 priority 映射） |
| timeframe | string | Y | 任意字符串 | 周期/路由提示（timeframe/route.horizon/context_snapshot.horizon） |
| evidence | object | Y | JSON object | 证据快照（优先 evidence，否则用 context_snapshot；并注入 trace + event_source/inference_source） |

实现：[active_events_redis.py](services/agent_server_new/adapters/active_events_redis.py#L117-L165)

时间字段归一化（active_events 适配器）：
- `evidence.event_ts_ms`：优先 `payload.event_ts_ms`，缺失回退 `payload.ts_ms`
- `evidence.processed_ts_ms`：优先 `payload.processed_ts_ms`，缺失回退 `payload.ts_ms`
- 该约束用于把 selected_event 的发生/处理时间语义稳定传到 agent 消费侧

来源语义归一化（active_events 适配器）：
- `source`：归一化后的事件来源（优先 `payload.source.name`，其次 `payload.source` 字符串，缺失回退 `event_center_new`）
- `evidence.event_source`：事件原始来源名（与 `source` 同语义，供下游显式消费）
- `evidence.event_source_category`：来源分类（当 `payload.source.category` 存在）
- `evidence.inference_source`：选择/推断来源（优先 `payload.trace.produced_by`，缺失回退 `event_center_new.selector`）

优先级到 score 的映射：

| priority | score |
|---|---:|
| high | 0.9 |
| medium | 0.6 |
| low | 0.3 |

实现：[active_events_redis.py](services/agent_server_new/adapters/active_events_redis.py#L94-L103)

#### 3.2.3 asset 匹配规则（精确匹配）

- 若 `asset` 形如 `exchange:symbol`：同时校验 exchange 与 symbol
- 若 `asset` 仅 symbol：必须与当前 symbol 完全相等（禁止子串匹配）

实现：[active_events_redis.py](services/agent_server_new/adapters/active_events_redis.py#L105-L116)

#### 3.2.4 上游 selected_event 的最小依赖面（contract guard）

agent 对 event_center_new selected_event 的最小依赖（用于持续集成守卫）：

- 必需字段：`asset, selected_type, direction_hint, priority, context_snapshot, route`

测试：[test_active_events_contract_guard.py](verification/auditors/agent_server_new/test_active_events_contract_guard.py#L19-L24)

### 3.3 PositionContextProvider（仓位上下文输入）

端口定义：`get_position_context(exchange, symbol) -> dict`  
定义：[position_context_provider.py](services/agent_server_new/ports/data/position_context_provider.py#L6-L10)

默认实现为 stub：

| 字段 | 类型 | 含义 |
|---|---|---|
| has_position | bool | 是否有仓位 |
| current_position | any | 当前仓位（占位） |
| avg_entry | any | 平均入场价（占位） |
| exposure | any | 暴露（占位） |
| margin | any | 保证金（占位） |
| portfolio_risk | any | 组合风险（占位） |

实现：[position_context_stub.py](services/agent_server_new/adapters/position_context_stub.py#L8-L21)

### 3.4 ExecutionDecisionProvider（可选下游：执行裁决）

端口定义：`decide(payload: dict) -> dict`  
定义：[decision_provider.py](services/agent_server_new/ports/execution/decision_provider.py#L6-L10)

HTTP 适配器：
- 调用：`POST {AGENT_EXECUTION_BASE_URL}/internal/execution/decide`
- 默认 base_url：`http://127.0.0.1:9962`

实现：[execution_service_http.py](services/agent_server_new/adapters/execution_service_http.py#L11-L36)

### 3.5 EventRecorder（可选输出：审计/回放）

端口定义：
- `record_market_context(event_id, payload)`
- `record_agent_output(event_id, agent_name, payload)`

定义：[event_recorder.py](services/agent_server_new/ports/event_recorder.py#L6-L13)

默认 bootstrap 未注入 recorder（为 None）：[bootstrap.py](services/agent_server_new/app/bootstrap.py#L86-L93)

### 3.6 SymbolMemory（可选输入/输出：symbol 级记忆）

端口：
- provider：`get_symbol_memory(exchange, symbol, limit) -> dict`：[symbol_memory_provider.py](services/agent_server_new/ports/memory/symbol_memory_provider.py#L6-L10)
- recorder：`record_symbol_memory(exchange, symbol, payload) -> None`：[symbol_memory_recorder.py](services/agent_server_new/ports/memory/symbol_memory_recorder.py#L6-L10)

适配器：
- inmemory：[symbol_memory_inmemory.py](services/agent_server_new/adapters/symbol_memory_inmemory.py)
- redis：[symbol_memory_redis.py](services/agent_server_new/adapters/symbol_memory_redis.py)

---

## 4. 默认装配（create_trade_event_workflow_from_env）

默认接线（重点）：

- market_state：`HttpMarketStateProvider.from_env()`
- position_context：`HttpExecutionPositionContextProvider.from_env(...)`
- active_events：由 `AGENT_ACTIVE_EVENTS_PROVIDER_MODE` 控制（默认 redis；仅在非生产且显式开启 `AGENT_ACTIVE_EVENTS_ALLOW_NULL_FALLBACK=true` 时才降级为 null provider）
- execution_decider：由 `AGENT_EXECUTION_ENABLED` 控制（默认 false）
- symbol_memory：由 `AGENT_SYMBOL_MEMORY_ENABLED` 控制（默认 false），backend=redis|inmemory

实现：[bootstrap.py](services/agent_server_new/app/bootstrap.py#L30-L99)

---

## 5. 工作流输入：TradeEventInput（触发事件最小集合）

数据结构：

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| event_id | string | Y | 事件 ID（建议稳定、可追踪） |
| exchange | string | Y | 交易所 |
| symbol | string | Y | 交易对 |
| signal_direction | string | Y | 上游信号方向提示（long/short/buy/sell 等） |
| payload | object | Y | 事件 payload（半结构化，agent 会从中抽取 event_type/timestamp 等） |

定义：[trade_event_workflow.py](services/agent_server_new/app/workflows/trade_event_workflow.py#L33-L42)

### 5.1 payload 中会被读取的“常见字段”（实现约定）

在 ContextBuilder 的证据裁剪逻辑中，会尝试从 payload 读取：

- `event_type` / `type` / `kind`：用于选择裁剪 profile（liquidation/macro_sentiment/indicator_signal/generic）
- `event_ts_ms / ts_ms / timestamp_ms / ts / generated_at_ms / timestamp`：用于 freshness 判断（strategy_gate_v2）

实现：
- profile 选择：[context_builder.py](services/agent_server_new/app/context_builder.py#L115-L124)
- ts 提取：[strategy_gate.py](services/agent_server_new/domain/strategy_gate.py#L77-L100)

---

## 6. ContextBuilder：输入聚合与 key_market_features 裁剪

### 6.1 输入与输出

输入：
- market_state（MarketStateSnapshot）
- position_context（dict）
- active_events（list[dict]，归一化后的 ActiveEvent）
- symbol_memory（可选）
- signal_payload（来自 TradeEventInput.payload）

输出：
- `BuiltContext.ctx`：`EventContext`（统一上下文，给 workflow 后续 stages）
- `BuiltContext.raw_market_structure`：审计用 raw_market_structure

实现：[context_builder.py](services/agent_server_new/app/context_builder.py#L182-L267)

### 6.2 EventContext 字段表

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| event_id | string | Y | 事件 ID |
| exchange | string | Y | 交易所 |
| symbol | string | Y | 交易对 |
| timestamp_ms | int | Y | 生成上下文时间（ms） |
| signal_event | object | Y | 统一的 signal_event（把 event_id/exchange/symbol/payload 打包） |
| msl | MarketStateMSL | Y | 状态层 MSL |
| key_market_features | object | Y | 裁剪后的关键证据（见 6.3） |
| active_events | array[object] | Y | 背景事件列表（ActiveEvent） |
| position_context | object | Y | 仓位上下文（当前 stub 或外部注入） |

定义：[event_context.py](services/agent_server_new/app/workflows/event_context.py#L10-L27)

### 6.3 key_market_features 结构（裁剪输出）

`key_market_features` 的结构固定为：

| 字段 | 类型 | 含义 |
|---|---|---|
| profile | string | 裁剪策略：liquidation / macro_sentiment / indicator_signal / generic |
| features | array[{name,value}] | Top-K 证据列表（最多 max_key_features；强制注入 cross_horizon/msl_meta/记忆） |
| evidence | object | 透传状态层 `state_features.evidence`（完整对象） |
| anomalies | object | 透传状态层 `state_features.anomalies`（完整对象） |
| memory_observability | object | 记忆注入统计（见 6.5） |

`alternative_source_summary`（当存在）会包含：
- `available_sources/unavailable_sources`
- `provider_states`
- `data_sources`（每类来源对应的数据来源标识）
- `inference_sources`（每类来源对应的推断来源标识）
- `feature_keys`
- `preferred_source/conflict_count`（仅 fusion 可用时）

结构单源：
- `contracts/schemas/alternative_source_summary.schema.json`

`provider_states` 枚举口径（agent 汇总视角）：
- `primary/fallback/static/noop/unavailable/empty/ok/event_evidence_present`
- 统一策略单源：`contracts/semantic_policies/source_semantics.yaml`

实现：[context_builder.py](services/agent_server_new/app/context_builder.py#L96-L180) 与 [context_builder.py](services/agent_server_new/app/context_builder.py#L245-L256)

### 6.4 features 列表：强制注入项 + 动态候选项

features 列表在 candidates 之前会**强制注入**：

- `{name:"cross_horizon", value: <market_state.cross_horizon>}`
- `{name:"msl_meta", value: <market_state.msl_meta>}`
- `{name:"memory_summary", value: <symbol_memory.summary>}`（若存在）
- `{name:"recent_memory", value: <symbol_memory.recent>}`（若存在）

实现：[context_builder.py](services/agent_server_new/app/context_builder.py#L159-L171)

动态候选项会按 profile 不同选择不同字段（示例）：

- liquidation：更强调清算/流动性/OI 风险（delta_oi_pct、oi_risk_flags、liquidation_cluster_flag 等）
- macro_sentiment：更强调 active_events_top / trend_context / participant_background
- generic：综合 orderbook、OI、trend_memory、trend_context 等

实现：[context_builder.py](services/agent_server_new/app/context_builder.py#L125-L178)

### 6.5 memory_observability 字段表（便于调试）

| 字段 | 类型 | 含义 |
|---|---|---|
| memory_hit | bool | summary 或 recent 任一非空视为命中 |
| memory_raw_recent_count | int | 原始 recent 数量 |
| memory_filtered_recent_count | int | 过滤后 recent 数量（TTL/topk/dedup 后） |
| memory_dropped_count | int | 被丢弃条数 |
| memory_summary_field_count | int | summary 字段数量 |
| memory_summary_event_count | int | summary.event_count（缺失为 0） |

实现：[context_builder.py](services/agent_server_new/app/context_builder.py#L75-L94)

---

## 7. workflow 分阶段输入输出

### 7.1 signal_evaluator：ExpertContext -> SignalVerdict

输入：`ExpertContext(msl, key_market_features, active_events, signal_event, position_context)`  
输出：`SignalVerdict(direction, verdict, confidence, invalidation_reasons, notes)`

字段枚举见 8.1~8.2。

示例实现（当前为规则占位，不接 LLM）：
- 若存在流动性真空/清算簇等结构风险：reject
- 若 regime=transition：uncertain
- 否则 accept

实现：[signal_evaluator.py](services/agent_server_new/experts/signal_evaluator.py#L11-L74)

### 7.2 intent_resolver：SignalVerdict + MSL + PositionContext -> ActionIntent

核心规则（当前实现）：
- 信号 reject：无仓位则 hold；有仓位则 decrease
- msl.anomalies 包含 liquidity_vacuum：hold
- msl.market_fragility=high 或 horizon_alignment=conflict：hold
- 信号 uncertain：有仓位倾向 decrease，否则 hold
- 信号 accept 且方向与 MSL direction_bias 冲突：hold
- market_phase=distribution/contraction：hold
- 否则 increase（direction=long/short）

实现：[intent_resolver.py](services/agent_server_new/domain/intent_resolver.py#L10-L112)

### 7.3 rule_planner：ActionIntent + MSL -> RulePlan（sizing 规则化）

sizing 输出字段（当前实现约定）：

| intent.intent | sizing.mode | sizing 字段 |
|---|---|---|
| increase | ratio | order_size_ratio, entry_type |
| decrease | ratio | partial_exit_ratio, entry_type |
| close | full | entry_type |
| hold | ratio（可选） | partial_exit_ratio（仅高脆弱时轻减） |

实现：[rule_planner.py](services/agent_server_new/domain/rule_planner.py#L10-L61)

### 7.4 horizon_policy_gate：cross_horizon -> GateResult

输入来自 `key_market_features.features` 的 `cross_horizon.value`：

| 字段 | 类型 | 典型枚举（来自状态层） |
|---|---|---|
| suggested_policy | string | follow_long_term / wait_confirmation / reduce_risk / no_action |
| policy_reason | string | 状态层生成的原因码（实现内为字符串） |

提取逻辑：[trade_event_workflow.py](services/agent_server_new/app/workflows/trade_event_workflow.py#L52-L63)

门控逻辑（默认配置）：
- 当 intent=increase 且 suggested_policy in {wait_confirmation, reduce_risk} 时阻断
- 阻断原因码主码来自单源常量：`horizon_policy_wait_confirmation | horizon_policy_reduce_risk | horizon_policy_blocked`
- 策略原因统一标准标签：`policy_reason:<code>`

实现：[horizon_policy_gate.py](services/agent_server_new/domain/horizon_policy_gate.py#L57-L69)
原因码单源：[horizon_policy_reasons.py](services/agent_server_new/domain/horizon_policy_reasons.py)

### 7.5 strategy_gate_v2：语义门控

关键阻断点（当前实现）：
- signal_stale：`msl.ts - signal_event_ts > 10min`
- fragility_high_block_increase：高脆弱性禁止 increase
- direction_bias_mismatch：MSL 方向偏置与信号方向冲突
- liquidity_vacuum：结构风险阻断
- horizon_conflict：跨周期冲突阻断 increase

原因码单源（防漂移）：[strategy_gate_reasons.py](services/agent_server_new/domain/strategy_gate_reasons.py)

实现：[strategy_gate.py](services/agent_server_new/domain/strategy_gate.py#L47-L84)

### 7.6 risk_gate：RiskGateContext -> RiskAllowance

RiskGateContext 枚举：
- global_regime：normal/elevated/critical
- cooldown_active：bool

当 global_regime=critical 或 cooldown_active=true 时：不允许 open/add，仅允许 reduce/exit。

实现：[risk_gate.py](services/agent_server_new/domain/risk_gate.py#L9-L42)
原因码单源（`decision_trace.risk_gate.regime_sources`）：[risk_gate_reasons.py](services/agent_server_new/domain/risk_gate_reasons.py)

### 7.7 execution_planner：RulePlan + RiskAllowance -> ExecutionPlan

动作映射：

| ActionIntentType | RiskAction |
|---|---|
| increase | add |
| decrease | reduce |
| close | exit |
| hold | hold |
| skip | skip |

若 allowance 不允许对应动作，会降级为 hold，并降低 confidence。

实现：[execution_planner.py](services/agent_server_new/domain/execution_planner.py#L8-L72)

### 7.8 execution_decider（可选）：ExecutionPlan -> execution_service DecisionIntent

workflow 会把 agent 的 ExecutionPlan 映射为 execution_service 侧的 DecisionIntent payload（当前冻结字段如下）：

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| decision_id | string | Y | 复用 event_id |
| exchange | string | Y | 交易所 |
| symbol | string | Y | 交易对 |
| direction_intent | string | Y | long/short/none（来自 plan.direction） |
| decision_confidence | object | Y | {level, score}（canonical） |
| cross_horizon_policy | object | Y | {suggested_policy, policy_reason} |
| risk_hints | object | Y | {agent_action_hint, agent_notes, decision_confidence, decision_confidence_source, decision_agent_key, decision_mode, llm_parse_status, prompt_config_source, prompt_config_version, signal_verdict, signal_reliability_score, signal_reasons} |

说明：
- 该链路默认不再发送 `confidence`（deprecated alias）。
- 若需兼容旧执行层入口，应通过 execution 侧兼容回填处理，而非在新 producer 恢复别名输出。

当启用 `AGENT_AI_ADAPTIVE_ENABLED=true` 时会追加保留字段：
- execution_hint / adaptive_profile / adaptive_profile_version / adaptive_explain

实现：[trade_event_workflow.py](services/agent_server_new/app/workflows/trade_event_workflow.py#L371-L408)

execution_service 的返回体在 agent 内部不做 schema 冻结（原样 dict 透传为 execution_result）。

---

## 8. agent 领域契约：字段枚举与说明（冻结）

### 8.1 Direction（方向）

定义：`Direction = "long" | "short" | "none"`  
来源：[domain/contracts.py](services/agent_server_new/domain/contracts.py#L7)

### 8.2 Confidence / SignalVerdict

Confidence：

| 字段 | 类型 | 枚举/范围 |
|---|---|---|
| level | string | high / medium / low |
| score | number | 0~1（约定） |

SignalVerdict：

| 字段 | 类型 | 枚举/范围 | 含义 |
|---|---|---|---|
| direction | Direction | long/short/none | 信号方向 |
| verdict | string | accept/reject/uncertain | 信号有效性裁决 |
| confidence | Confidence |  | 置信度 |
| invalidation_reasons | array[string] |  | 失效原因列表 |
| notes | string |  | 备注 |

来源：[domain/contracts.py](services/agent_server_new/domain/contracts.py#L12-L29)

### 8.3 ActionIntent / RulePlan / RiskAllowance / ExecutionPlan

ActionIntentType（动作意图）：
- increase / decrease / close / hold / skip

RiskAction（执行动作）：
- add / reduce / hold / exit / skip

RiskAllowance：

| 字段 | 类型 | 含义 |
|---|---|---|
| allow_open | bool | 是否允许开仓 |
| allow_add | bool | 是否允许加仓 |
| allow_reduce | bool | 是否允许减仓 |
| allow_exit | bool | 是否允许平仓 |
| reasons | array[string] | 禁止原因 |

ExecutionPlan：

| 字段 | 类型 | 含义 |
|---|---|---|
| action | RiskAction | 最终动作 |
| direction | Direction | 方向 |
| allowance | RiskAllowance | 风控许可 |
| confidence | Confidence | 置信度 |
| sizing | object\|null | sizing（由 rule_planner 产出并可被约束合并） |
| notes | string | 说明 |

来源：[domain/contracts.py](services/agent_server_new/domain/contracts.py#L31-L72)

---

## 8.4 附录：agent 对 MSL 的最小依赖面（字段与枚举）

`agent_server_new` 不定义 MSL 的生产逻辑，只消费 `market_state_engine` 输出的 MSL。为了让本文件在阅读时自洽，这里列出 agent 侧会直接读取/判定的 MSL 字段与其枚举范围（以 `market_state_engine/docs/msl.schema.json` 为准）。

### 8.4.1 agent 直接读取的 MSL 字段（实现落点）

| 字段 | 用途 | 读取位置（示例） |
|---|---|---|
| msl.anomalies | 结构风险标签（liquidation_cluster/liquidity_vacuum 等） | [signal_evaluator.py](services/agent_server_new/experts/signal_evaluator.py#L35-L48)、[intent_resolver.py](services/agent_server_new/domain/intent_resolver.py#L31-L39)、[strategy_gate.py](services/agent_server_new/domain/strategy_gate.py#L48-L67) |
| msl.horizon_alignment | 跨周期冲突门控 | [signal_evaluator.py](services/agent_server_new/experts/signal_evaluator.py#L45-L46)、[intent_resolver.py](services/agent_server_new/domain/intent_resolver.py#L50-L57)、[strategy_gate.py](services/agent_server_new/domain/strategy_gate.py#L69-L70) |
| msl.regime | 过渡期处理（uncertain/hold） | [signal_evaluator.py](services/agent_server_new/experts/signal_evaluator.py#L59-L66) |
| msl.market_fragility | 脆弱性门控与 sizing 调整 | [intent_resolver.py](services/agent_server_new/domain/intent_resolver.py#L41-L48)、[rule_planner.py](services/agent_server_new/domain/rule_planner.py#L33-L39)、[strategy_gate.py](services/agent_server_new/domain/strategy_gate.py#L59-L61) |
| msl.direction_bias | 信号方向一致性检查 | [intent_resolver.py](services/agent_server_new/domain/intent_resolver.py#L86-L94)、[strategy_gate.py](services/agent_server_new/domain/strategy_gate.py#L62-L65) |
| msl.market_phase | 风险阶段下的扩张抑制 | [intent_resolver.py](services/agent_server_new/domain/intent_resolver.py#L96-L103) |
| msl.volatility.volatility_regime | sizing 调整与减仓比例 | [rule_planner.py](services/agent_server_new/domain/rule_planner.py#L30-L39)、[rule_planner.py](services/agent_server_new/domain/rule_planner.py#L45-L48) |
| msl.liquidity.liquidity_risk + msl.positioning.crowding | 结构风险组合判定 | [signal_evaluator.py](services/agent_server_new/experts/signal_evaluator.py#L43-L44) |

### 8.4.2 关键枚举（来自 MSL schema）

| 字段 | 枚举 |
|---|---|
| market_regime.trend | bullish / bearish / sideways / unknown |
| market_regime.phase | impulse / continuation / exhaustion / accumulation / distribution / unknown |
| market_regime.timeframe_alignment | aligned / mixed / conflicting / unknown |
| liquidity_state.liquidity_risk | short_squeeze / long_squeeze / neutral / unknown |
| positioning_state.crowding | crowded_long / crowded_short / balanced / unknown |
| volatility_state.volatility_regime | low / normal / high / unknown |
| market_risk_state.cascade_risk | high / medium / low / unknown |
| market_risk_state.squeeze_probability | high / medium / low / unknown |
| market_risk_state.reversal_risk | high / medium / low / unknown |

完整字段与枚举定义参考：
- [msl.schema.json](services/market_state_engine/docs/msl.schema.json)
- [market_state_engine_data_pipeline.md](docs/contracts/pipelines/market_state_engine_data_pipeline.md)

---

## 9. DecisionTrace（可观测输出）

当 recorder 存在时，workflow 会写出 `decision_trace`（agent_name="decision_trace"）：

| 字段 | 类型 | 含义 |
|---|---|---|
| event_id/exchange/symbol/ts | 基础字段 | 追踪标识与时间 |
| event | object | signal_event 的快照 |
| msl | object | `msl.to_llm_dict()` 输出 |
| key_features | object | key_market_features（包含裁剪 features 列表） |
| evidence/anomalies | object | 从 key_market_features 拿的 evidence/anomalies（通常来自 state_features） |
| signal_verdict/intent/rule_plan | object | 各阶段关键输出摘要 |
| strategy_gate_result/risk_gate/execution_plan | object | 门控与计划摘要（其中 strategy_gate_result 包含 `horizon_reasons/strategy_reasons/reasons`） |
| llm_observation | object | LLM 旁路观察摘要（`status/provider/model/raw_content_hash`，失败或禁用也会输出固定语义） |
| memory_metrics | object | memory_observability |
| tags | array[string] | 标签（当前固定含 decision_trace） |

结构定义：[decision_trace.py](services/agent_server_new/observability/decision_trace.py#L7-L51)  
契约 schema：[decision_trace.schema.json](services/agent_server_new/docs/decision_trace.schema.json)  
构建与写出：[trade_event_workflow.py](services/agent_server_new/app/workflows/trade_event_workflow.py#L285-L337)

可追溯性示例测试（selected_event -> active_events -> decision_trace）：
- [test_pipeline_traceability_contract.py](verification/auditors/agent_server_new/test_pipeline_traceability_contract.py#L131-L203)

---

## 10. 运行期环境变量（实现对齐）

### 10.1 状态层 HTTP

| 变量 | 默认值 | 含义 |
|---|---|---|
| AGENT_MARKET_STATE_BASE_URL | http://127.0.0.1:8300 | market_state_engine base URL |
| AGENT_MARKET_STATE_TIMEOUT_S | 10 | HTTP 超时（秒） |

来源：[market_state_http.py](services/agent_server_new/adapters/market_state_http.py#L63-L72)

### 10.2 active_events（Redis）

| 变量 | 默认值 | 含义 |
|---|---|---|
| AGENT_ACTIVE_EVENTS_PROVIDER_MODE | redis | 仅支持 redis |
| AGENT_ACTIVE_EVENTS_ALLOW_NULL_FALLBACK | false | 非生产环境是否允许 Redis 初始化失败回退 null provider |
| AGENT_ACTIVE_EVENTS_REDIS_URL | redis://127.0.0.1:6379/0 | Redis 连接串 |
| AGENT_ACTIVE_EVENTS_STREAM | ec:selected | Stream key |
| AGENT_ACTIVE_EVENTS_LIMIT_DEFAULT | 20 | 返回条数 |
| AGENT_ACTIVE_EVENTS_SCAN_FACTOR | 5 | 扫描倍率（count = limit * factor） |

来源：[bootstrap.py](services/agent_server_new/app/bootstrap.py#L40-L75) 与 [active_events_redis.py](services/agent_server_new/adapters/active_events_redis.py#L19-L36)

### 10.3 execution_decider（execution_service）

| 变量 | 默认值 | 含义 |
|---|---|---|
| AGENT_EXECUTION_ENABLED | false | 是否启用 execution_decider |
| AGENT_EXECUTION_BASE_URL | http://127.0.0.1:9962 | execution_service base URL |
| AGENT_EXECUTION_TIMEOUT_S | 10 | HTTP 超时（秒） |

来源：[bootstrap.py](services/agent_server_new/app/bootstrap.py#L48-L53) 与 [execution_service_http.py](services/agent_server_new/adapters/execution_service_http.py#L18-L28)

### 10.4 symbol_memory（可选）

| 变量 | 默认值 | 含义 |
|---|---|---|
| AGENT_SYMBOL_MEMORY_ENABLED | false | 是否启用 symbol memory |
| AGENT_SYMBOL_MEMORY_BACKEND | inmemory | inmemory/redis |
| AGENT_SYMBOL_MEMORY_CONTEXT_TOPK | 5 | 注入 recent_memory 条数 |
| AGENT_SYMBOL_MEMORY_CONTEXT_TTL_MS | 86400000 | recent_memory TTL（ms） |
| AGENT_SYMBOL_MEMORY_CONTEXT_DEDUP_KEY | event_id | recent_memory 去重键 |

Redis backend 额外变量（节选）：
- AGENT_SYMBOL_MEMORY_REDIS_URL
- AGENT_SYMBOL_MEMORY_RAW_KEY_TEMPLATE / SUMMARY_KEY_TEMPLATE / INDEX_KEY
- AGENT_SYMBOL_MEMORY_TTL_SECONDS / RAW_TOPK

来源：[bootstrap.py](services/agent_server_new/app/bootstrap.py#L54-L99) 与 [symbol_memory_redis.py](services/agent_server_new/adapters/symbol_memory_redis.py#L32-L74)

### 10.5 跨周期门控配置

| 变量 | 默认值 | 含义 |
|---|---|---|
| AGENT_HORIZON_POLICY_BLOCK_ON_INCREASE | ""（默认逻辑为 wait_confirmation,reduce_risk） | increase 时阻断的 suggested_policy 列表（CSV） |
| AGENT_HORIZON_POLICY_CONFIG_JSON | "" | JSON 覆盖配置 |

来源：[horizon_policy_gate.py](services/agent_server_new/domain/horizon_policy_gate.py#L22-L45)

### 10.6 AI adaptive（保留字段）

| 变量 | 默认值 | 含义 |
|---|---|---|
| AGENT_AI_ADAPTIVE_ENABLED | false | 是否向 execution_service 发送保留的 adaptive 字段 |
| AGENT_AI_ADAPTIVE_MODE | observe | observe/recommend/bounded_apply |

来源：[bootstrap.py](services/agent_server_new/app/bootstrap.py#L79-L99) 与 [trade_event_workflow.py](services/agent_server_new/app/workflows/trade_event_workflow.py#L399-L408)
