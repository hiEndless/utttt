# execution_service 数据流水线与字段契约（实现对齐版）

本文档面向 `/services/execution_service` 当前代码实现，按“真实执行顺序”梳理执行层的数据链路：从 `DecisionIntent`（agent 意图）进入，到幂等/状态读取/风控规则评估/（可选）执行下沉与对账，再到 `ExecutionResult` 与 `DecisionState` 的产出与落盘。文档包含各环节输入输出、字段枚举与字段说明。

主要依据：
- App 装配与运行期配置：[app/__init__.py](services/execution_service/app/__init__.py)
- HTTP 路由入口：[routes.py](services/execution_service/routes.py)
- Service 主链路（幂等/状态机/submit/reconcile）：[app/service.py](services/execution_service/app/service.py)
- 核心契约（DecisionIntent/ExecutionResult）：[domain/contracts.py](services/execution_service/domain/contracts.py)
- 决策引擎入口：[decision_engine.py](services/execution_service/domain/decision_engine.py)
- 风控规则与优先级：[risk_rules.py](services/execution_service/domain/risk_rules.py)
- 风控检查结构化明细：[risk_check_builder.py](services/execution_service/domain/risk_check_builder.py)
- 风控状态与迁移原因码：[risk_states.py](services/execution_service/domain/risk_states.py)、[risk_state_change_reasons.py](services/execution_service/domain/risk_state_change_reasons.py)
- Redis key 契约：[redis_keys.md](services/execution_service/docs/redis_keys.md)
- Schema/枚举冻结（输入/输出/中间结果）：[execution_enums.schema.json](services/execution_service/docs/execution_enums.schema.json)
- 模块边界声明：[boundaries.md](services/execution_service/docs/boundaries.md)

时间语义口径（canonical）：`docs/contracts/SEMANTIC_GLOSSARY.md`
- execution API 元信息时间字段保持 `ts/ts_ms`（兼容保留）
- execution 不直接消费事件层 `event_ts_ms/processed_ts_ms`
- 若上游（agent/event）已归一化到 `event_ts_ms/processed_ts_ms`，execution 侧不应改写其语义含义

---

## 0. 总览：端到端“真实执行顺序”

以 `POST /internal/execution/decide` 为主链路：

1. HTTP 路由接收 payload（dict），调用 `ExecutionService.decide(payload)`
2. 输入解析与强校验：`DecisionIntent.from_dict(payload)`
3. 幂等缓存：
   - 命中缓存：直接返回首次 `ExecutionResult`
   - 未命中：抢占处理锁；抢不到返回 `execution_action=skip` + `reject_reason=idempotency_in_progress`
4. 写入决策状态机 `pending`（可选开启）
5. 从三类 Provider 拉取快照：
   - PositionState（仓位）
   - AccountState（账户）
   - RiskPolicy（风控策略）
6. 进入 `ExecutionDecisionEngine.decide(...)`：
   - 调用 `evaluate_risk_rules(decision, RiskContext(...))`
   - 构造 `signal_result`（含 risk_checks/risk_state/rule_debug/position_simulation 等）
7. Service 侧补齐 `policy_snapshot`（policy_version/ruleset_hash，可选 agent_prompt_config_version）
8. （可选）执行下沉 submit：`execution_sink.submit(decision, execution_action)`，并写入 `order_result`
9. 写入幂等结果缓存（可选开启）
10. 写入决策状态机终态（decided/submitted/skipped/failed）
11. 返回 `ExecutionResult`

核心入口与顺序：
- 路由：[routes.py](services/execution_service/routes.py#L40-L48)
- Service：[app/service.py](services/execution_service/app/service.py#L69-L166)
- Engine：[decision_engine.py](services/execution_service/domain/decision_engine.py#L9-L37)

---

## 1. 模块边界（职责声明）

`execution_service` 的责任边界（实现对齐）：

- 输入允许：
  - agent 的决策意图（方向、置信度、解释提示）
  - 仓位/账户状态（通过 Provider）
  - 风控策略配置（risk_policy）
- 输入不允许：
  - 原始行情数据
  - 特征层 raw structure
  - 事件中心原始事件流
- 输出只包含执行层结果：
  - 最终动作（execution_action）
  - 拒绝原因（reject_reason）
  - 应用规则（applied_risk_rules）
  - 执行回执（order_result，可选）

来源：[boundaries.md](services/execution_service/docs/boundaries.md)

---

## 2. HTTP API（对外接口）

路由前缀：`/internal/execution`

### 2.1 GET /healthz

返回字段：

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| ok | bool | Y | 固定 true |
| service | string | Y | 固定 "execution_service" |
| ts | int | Y | 当前毫秒时间戳 |
| ts_ms | int | Y | 同 ts |

实现：[routes.py](services/execution_service/routes.py#L21-L25)

### 2.2 GET /version

返回字段（用于排查契约/规则/状态机版本漂移）：

| 字段 | 类型 | 含义 |
|---|---|---|
| contract_version | string | 契约版本 |
| ruleset_version | string | 风控规则版本 |
| state_machine_version | string | 状态机版本 |
| idempotency_version | string | 幂等版本 |
| schema_mapping_version | string | schema 映射版本 |

实现：[routes.py](services/execution_service/routes.py#L26-L38) 与 [version.py](services/execution_service/version.py#L3-L7)

### 2.3 POST /decide（主链路）

输入：DecisionIntent（见 3）  
输出：ExecutionResult（见 7）

实现：[routes.py](services/execution_service/routes.py#L40-L48)

### 2.4 POST /reconcile（回执对账链路）

用于“订单回执/订单状态同步”：

- 幂等 key：`reconcile:{order_id}`（复用 idempotency_store）
- 若 sink 未配置：503
- 若 sink 不支持 reconcile：501
- 异常：502
- 非异常失败：HTTP 200，`status=failed` + `reason_code`（见 9）

实现：[routes.py](services/execution_service/routes.py#L50-L67) 与 [app/service.py](services/execution_service/app/service.py#L209-L328)

### 2.5 GET /debug/state/{exchange}/{symbol}

只读调试视图：返回当前 provider 读取到的 position_state/account_state/risk_policy，以及可选 decision_state。

实现：[routes.py](services/execution_service/routes.py#L68-L91) 与 [app/service.py](services/execution_service/app/service.py#L167-L201)

### 2.6 GET /debug/confidence-metrics 与 reset

用于迁移期统计：
- decide 请求是否仍在使用旧字段 `confidence`
- 是否存在 `confidence` 与 `decision_confidence` 不一致导致的拒绝

实现：[routes.py](services/execution_service/routes.py#L93-L110) 与 [confidence_metrics_store.py](services/execution_service/adapters/confidence_metrics_store.py#L10-L78)

---

## 3. 输入契约：DecisionIntent（agent -> execution）

### 3.1 DecisionIntent 字段表（强校验）

Schema：[decision_intent.schema.json](services/execution_service/docs/decision_intent.schema.json)  
解析与强校验：[DecisionIntent.from_dict](services/execution_service/domain/contracts.py#L48-L99)

| 字段 | 类型 | 必填 | 枚举/范围 | 含义 |
|---|---|:---:|---|---|
| decision_id | string | Y | 非空 | 决策唯一 ID（幂等主键） |
| exchange | string | Y | 非空 | 交易所（如 binance） |
| account_id | string | Y | 非空 | 账户 ID（默认 main） |
| symbol | string | Y | 非空 | 交易对（如 ETHUSDT） |
| direction_intent | string | Y | long/short/none | 方向意图（不是最终动作） |
| decision_confidence | object | Y | 见 3.2 | 语义主字段：置信度 |
| confidence | object | N | 见 3.2 | 兼容字段（deprecated），仅用于迁移窗口；producer 默认不应发送 |
| cross_horizon_policy | object | Y | 任意对象 | 跨周期策略摘要（透传，用于风控解释/trace，不做强语义约束） |
| risk_hints | object | Y | 任意对象 | 风险提示/解释/补充字段（用于下单侧推导，如 position_side/order_qty 等） |
| trace_id | string\|null | N |  | 追踪 ID（写入 decision_state） |

### 3.2 DecisionConfidence 枚举与范围

Schema：[decision_confidence.schema.json](services/execution_service/docs/decision_confidence.schema.json)

| 字段 | 类型 | 枚举/范围 |
|---|---|---|
| level | string | low/medium/high |
| score | number | [0,1] |

### 3.3 direction_intent 与 execution_action 枚举

枚举来源：[execution_enums.schema.json](services/execution_service/docs/execution_enums.schema.json)

| 字段 | 枚举 |
|---|---|
| direction_intent | long / short / none |
| execution_action | add / reduce / hold / exit / skip |

---

## 4. 幂等（Idempotency）与并发锁

当启用 `IdempotencyStore` 时：

1. `get_result(decision_id)` 命中：直接返回首次 ExecutionResult
2. 未命中：`try_acquire_lock(decision_id, ttl_s)` 抢占处理锁
3. 抢占失败：
   - 若随后读到缓存：返回缓存
   - 否则返回降级结果：`execution_action=skip`、`reject_reason=idempotency_in_progress`

实现：
- 主逻辑：[app/service.py](services/execution_service/app/service.py#L79-L99)
- Redis key 模板：[idempotency_store.py](services/execution_service/adapters/idempotency_store.py#L36-L68)

幂等相关 reject_reason（枚举冻结）：[reject_reason.schema.json](services/execution_service/docs/reject_reason.schema.json#L6-L20)

---

## 5. 状态读取：PositionState / AccountState / RiskPolicy

### 5.1 三类 Provider（Ports）

`ExecutionService` 通过三个 Provider 拉取快照：

- PositionStateProvider：仓位状态
- AccountStateProvider：账户状态
- RiskPolicyProvider：风控策略

注入位置：[ExecutionService.__init__](services/execution_service/app/service.py#L38-L67)

### 5.2 Redis 模式与 key 模板

当 `EXECUTION_STATE_PROVIDER_MODE=redis` 时：

- 仓位：`execution:position:{exchange}:{account_id}:{symbol}`
- 账户：`execution:account:{exchange}:{account_id}`
- 风控策略：`execution:risk_policy:{exchange}:{symbol}`

来源：[RedisExecutionStateConfig](services/execution_service/adapters/redis_state_providers.py#L57-L87) 与 [redis_keys.md](services/execution_service/docs/redis_keys.md#L7-L86)

### 5.3 execution_service 消费侧的“最小字段子集”

#### 5.3.1 PositionState（consumer 侧字段）

Redis 适配器会补齐默认值并输出以下字段（字段缺失不报错）：

| 字段 | 类型 | 含义 |
|---|---|---|
| position_mode | string | one_way/hedge（仓位模式） |
| position_side | string | flat/long/short（净仓方向） |
| position_size | number | 净仓规模（兼容字段） |
| long_position_size | number | 多头腿规模（hedge 模式更关键） |
| short_position_size | number | 空头腿规模 |
| max_position_size | number | 默认仓位上限（兼容字段） |
| unrealized_pnl | number | 浮动盈亏（debug 可脱敏） |
| cooldown_seconds_left | int | 冷却剩余秒数（>0 禁止新增风险） |

实现：[RedisPositionStateProvider](services/execution_service/adapters/redis_state_providers.py#L90-L119)

#### 5.3.2 AccountState（consumer 侧字段）

| 字段 | 类型 | 含义 |
|---|---|---|
| account_equity | number | 账户净值（用于暴露比例计算） |
| available_balance | number | 可用余额（用于最小余额门控） |
| margin_ratio | number | 保证金率（用于阈值门控） |
| max_drawdown_ratio | number | 最大回撤阈值（缺省 0.15） |
| current_drawdown_ratio | number | 当前回撤比率 |
| daily_loss | number | 当日亏损（缺省 0） |
| consecutive_loss_count | int | 连亏次数 |
| risk_state | string | normal/warn/reduce_only/frozen（用于前态记忆/状态防抖） |

实现：[RedisAccountStateProvider](services/execution_service/adapters/redis_state_providers.py#L122-L149)

#### 5.3.3 RiskPolicy（consumer 侧字段）

| 字段 | 类型 | 含义 |
|---|---|---|
| position_mode | string | one_way/hedge（优先生效于 position_state） |
| allow_dual_side | bool | 是否允许双向持仓（hedge） |
| max_position_size / max_long_position_size / max_short_position_size | number | 仓位上限 |
| min_available_balance | number | 最小可用余额 |
| max_drawdown_ratio | number | 最大回撤阈值 |
| max_symbol_exposure_ratio | number | 单 symbol 暴露占比上限 |
| max_account_notional | number | 账户总敞口上限 |
| max_margin_ratio | number | 保证金率上限 |
| max_daily_loss | number | 当日亏损上限 |
| max_consecutive_loss_count | int | 连亏上限 |
| simulation_step_size | number | position_after_simulation 的步长 |
| rule_priority_order | array[string] | 规则优先级顺序（必须为 8 项完整排列，否则回退默认） |

实现：[RedisRiskPolicyProvider](services/execution_service/adapters/redis_state_providers.py#L152-L198)

---

## 6. 风控决策链路：DecisionIntent -> RiskContext -> RuleOutcome

### 6.1 RiskContext（中间上下文）

定义：`RiskContext(position_state, account_state, risk_policy)`  
来源：[risk_rules.py](services/execution_service/domain/risk_rules.py#L25-L32)

### 6.2 规则优先级（冻结与可配置）

默认优先级（高 -> 低）：

1. position_limit
2. cooldown
3. max_drawdown
4. account_notional
5. margin_ratio
6. daily_loss
7. consecutive_loss
8. direction_conflict

来源：[risk_rules.py](services/execution_service/domain/risk_rules.py#L35-L53)

配置覆盖规则（强约束）：
- `risk_policy.rule_priority_order` 必须是与默认集合完全相同的 8 项排列（长度、去重、集合必须完全一致），否则回退默认顺序。

实现：[risk_rules.py](services/execution_service/domain/risk_rules.py#L377-L388)

### 6.3 风控检查明细（risk_checks）

在执行规则判断之前，系统会构造结构化 `risk_checks`，用于输出 `signal_result.risk_checks`：

每条 check 字段：

| 字段 | 类型 | 枚举/范围 | 含义 |
|---|---|---|---|
| check | string | 见 6.3.1 | 检查码 |
| scope | string | account/symbol/position | 作用域 |
| status | string | pass/fail | 是否通过 |
| value | number |  | 当前值 |
| threshold | number |  | 阈值 |
| message_zh | string | 非空 | 标准化中文说明 |

构造实现：[risk_check_builder.py](services/execution_service/domain/risk_check_builder.py#L36-L166)  
Schema：[risk_checks.schema.json](services/execution_service/docs/risk_checks.schema.json)

#### 6.3.1 risk_checks.check 枚举（冻结）

来源：Schema + 代码常量单点定义：
- [risk_checks.schema.json](services/execution_service/docs/risk_checks.schema.json#L12-L24)
- [risk_check_codes.py](services/execution_service/domain/risk_check_codes.py#L4-L24)

枚举值：
- account_drawdown_limit
- account_available_balance
- account_notional_limit
- account_margin_ratio_limit
- account_daily_loss_limit
- account_consecutive_loss_limit
- symbol_exposure_ratio
- long_leg_position_limit
- short_leg_position_limit

#### 6.3.2 scope/status 枚举（冻结）

来源：[risk_check_meta.py](services/execution_service/domain/risk_check_meta.py#L4-L20)

| 字段 | 枚举 |
|---|---|
| scope | account / symbol / position |
| status | pass / fail |

### 6.4 规则命中后的输出要点（确定性裁决）

每条规则命中会返回：

- execution_action（add/reduce/hold/exit/skip）
- reject_reason（可为空；非空表示“拒绝/降级原因”）
- applied_risk_rules（用于审计/调试，字符串数组）
- notes（中文说明）
- hit_rule/hit_rule_value/hit_rule_threshold（用于 rule_debug 与解释）

命中实现示例（节选）：
- 仓位上限：[risk_rules.py](services/execution_service/domain/risk_rules.py#L391-L419)
- 冷却期：[risk_rules.py](services/execution_service/domain/risk_rules.py#L422-L433)
- 最大回撤：[risk_rules.py](services/execution_service/domain/risk_rules.py#L436-L451)
- 方向冲突（单向仓位时返回 reduce）：[risk_rules.py](services/execution_service/domain/risk_rules.py#L454-L476)
- 账户敞口/保证金率/当日亏损/连亏：[risk_rules.py](services/execution_service/domain/risk_rules.py#L478-L547)

---

## 7. 输出契约：ExecutionResult（execution -> 上游消费者）

### 7.1 ExecutionResult 字段表（强校验）

Schema：[execution_result.schema.json](services/execution_service/docs/execution_result.schema.json)  
解析与强校验：[ExecutionResult.from_dict](services/execution_service/domain/contracts.py#L131-L180)

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| decision_id | string | Y | 决策 ID（与输入一致） |
| execution_action | string | Y | 最终动作（见 3.3） |
| reject_reason | string\|null | Y | 拒绝/降级原因码（见 7.2） |
| applied_risk_rules | array[string] | Y | 应用到的规则名/标签（审计用途） |
| order_result | object | N | 执行下沉回执（submit 或 reconcile 的输出） |
| signal_result | object | N | 风控评估明细（见 8） |
| policy_snapshot | object | N | 当前策略快照（policy_version/ruleset_hash，可选 agent_prompt_config_version） |
| notes | string | N | 中文说明 |

### 7.2 reject_reason 枚举（冻结）

Schema：[reject_reason.schema.json](services/execution_service/docs/reject_reason.schema.json)

- position_limit_reached
- cooldown_active
- max_drawdown_exceeded
- account_notional_exceeded
- account_margin_ratio_exceeded
- daily_loss_exceeded
- consecutive_loss_exceeded
- direction_conflict_with_position
- execution_submit_failed
- idempotency_in_progress
- null（表示未拒绝）

注意：
- `reject_reason` 非空意味着“本次执行被拒绝或已降级处理”；上游不应把它当作“中性通过”。

### 7.3 policy_snapshot（版本快照）

Schema：[policy_snapshot.schema.json](services/execution_service/docs/policy_snapshot.schema.json)  
构造实现（缺省回退）：[_build_policy_snapshot](services/execution_service/app/service.py#L502-L510)

| 字段 | 类型 | 含义 |
|---|---|---|
| policy_version | string | 生效策略版本（缺省 risk-policy-default-v1） |
| ruleset_hash | string | 规则集 hash/版本（缺省 RULESET_VERSION） |
| agent_prompt_config_version | string | 可选，透传 agent 侧 decision_prompt 配置版本（来自 risk_hints.prompt_config_version） |

---

## 8. signal_result（风控评估明细输出）

### 8.1 ExecutionSignalResult 字段结构

Schema：[execution_signal_result.schema.json](services/execution_service/docs/execution_signal_result.schema.json)

| 字段 | 类型 | 必填 | 含义 |
|---|---|:---:|---|
| signal_action | string | Y | 执行动作语义（见 8.2） |
| risk_state | string | N | 风控态势（见 8.3），用于上游监控/门控 |
| mode | string | Y | 当前固定 simulated |
| scope | object | Y | {exchange, account_id, symbol} |
| position_before | object | Y | 执行前仓位（含 mode/legs/net） |
| position_after_simulation | object | Y | 用 step_size 模拟的执行后仓位 |
| risk_checks | array[object] | Y | 结构化检查明细（见 6.3） |
| rule_debug | object | N | 规则命中/顺序/状态迁移/trace（见 8.4） |

构造实现：[risk_result_builder.py](services/execution_service/domain/risk_result_builder.py#L14-L92)

### 8.2 signal_action 枚举（冻结）

Schema：[signal_action.schema.json](services/execution_service/docs/signal_action.schema.json)

- add_long / add_short
- reduce_long / reduce_short
- hold / skip / exit_all

生成规则（例如 reduce 在 hedge 模式下按对冲腿处理）：
[_build_signal_action](services/execution_service/domain/risk_result_builder.py#L95-L124)

### 8.3 risk_state 枚举（冻结）

Schema：[risk_state.schema.json](services/execution_service/docs/risk_state.schema.json)  
代码单点定义：[risk_states.py](services/execution_service/domain/risk_states.py#L4-L14)

- normal：正常
- warn：预警（接近阈值/压力升高）
- reduce_only：仅允许减仓/降风险
- frozen：冻结（高风险，禁止扩张）

### 8.4 rule_debug（规则调试/回放载体）

Schema：[rule_debug.schema.json](services/execution_service/docs/rule_debug.schema.json)

关键字段：

| 字段 | 含义 |
|---|---|
| hit_rule | 命中规则名（未命中为 "none"） |
| rule_priority_order | 本次评估使用的 8 项规则顺序 |
| hit_rule_value / hit_rule_threshold | 命中值与阈值（可为空） |
| previous_risk_state / current_risk_state | 风控态势迁移前后 |
| risk_state_change_reason / _zh | 迁移原因码与中文解释（见 8.5） |
| matched_at_ms | 命中时间戳 |
| evaluation_trace | 每条规则的 pass/fail 轨迹（见 8.6） |

构造实现：[risk_result_builder.py](services/execution_service/domain/risk_result_builder.py#L56-L72)

### 8.5 risk_state_change_reason 枚举（冻结）

Schema：[risk_state_change_reason.schema.json](services/execution_service/docs/risk_state_change_reason.schema.json)  
代码单点定义与中文解释：[risk_state_change_reasons.py](services/execution_service/domain/risk_state_change_reasons.py#L4-L24)

- reject_frozen
- reject_reduce_only
- pressure_warn
- hysteresis_soften
- default_normal

### 8.6 evaluation_trace（规则轨迹）

Schema：[evaluation_trace.schema.json](services/execution_service/docs/evaluation_trace.schema.json)

每条轨迹字段：

| 字段 | 含义 |
|---|---|
| order | 评估顺序（从 1 开始） |
| rule | 规则名 |
| scope | account/symbol/position |
| status | pass/fail |
| value / threshold | 数值与阈值（可为空） |
| note_zh | 标准化中文说明 |

---

## 9. 执行下沉与对账（ExecutionSink）

### 9.1 submit（可选）

触发条件（全部满足才 submit）：

- `EXECUTION_SUBMIT_ENABLED=true`
- execution_sink 已装配
- `reject_reason is None`
- `execution_action in {"add","reduce","exit"}`

实现：[app/service.py](services/execution_service/app/service.py#L134-L141)

submit 重试与降级：
- 失败会指数退避重试（可配置）
- 重试仍失败：不抛 5xx，降级为 `execution_action=skip` + `reject_reason=execution_submit_failed`，并在 `order_result.retry_meta` 写入失败信息

实现：[_submit_with_retry](services/execution_service/app/service.py#L359-L410)

#### 9.1.1 order_result.retry_meta 字段

Schema：[retry_meta.schema.json](services/execution_service/docs/retry_meta.schema.json)

| 字段 | 类型 | 含义 |
|---|---|---|
| attempts | int | 实际尝试次数（>=1） |
| max_retries | int | 最大重试次数（>=0） |
| status | string | ok/failed |
| retryable | bool | reconcile 失败时用于表示是否可重试 |
| last_error | string | submit 失败时记录最后错误 |

### 9.2 reconcile（回执对账，可选）

对账输出（成功或失败）都会返回 HTTP 200 的 JSON；失败场景用 `status=failed + reason_code` 表达，不抛异常中断业务（除 sink 缺失/不支持等）。

对账状态枚举（冻结）：[reconcile_statuses.py](services/execution_service/domain/reconcile_statuses.py#L4-L16)
- submitted / filled / canceled / rejected / failed

对账失败原因码（冻结）：[reconcile_codes.py](services/execution_service/domain/reconcile_codes.py#L4-L12)
- reconcile_retry_exhausted
- reconcile_non_retryable_error
- reconcile_in_progress

对账实现：[ExecutionService.reconcile_order](services/execution_service/app/service.py#L209-L282) 与 [_reconcile_with_retry](services/execution_service/app/service.py#L283-L328)

---

## 10. 决策状态机（DecisionStateStore）

当启用 `ExecutionStateStore` 时，service 会写入并维护 `DecisionState`：

- 决策开始写 `pending`
- 决策完成写终态：decided/submitted/skipped/failed
- reconcile 可把状态推进到 submitted/filled/canceled/rejected/failed（取决于回执 status）
- 状态跃迁有白名单校验，非法跃迁会被拒绝（仅记录 warning，不覆盖旧状态）

跃迁规则实现：[_is_valid_state_transition](services/execution_service/app/service.py#L423-L437)

### 10.1 DecisionState 字段表（Schema 冻结）

Schema：[decision_state.schema.json](services/execution_service/docs/decision_state.schema.json)

必需字段：
- decision_id、account_id、status、last_transition、attempts、source、updated_at_ms

status 枚举（冻结）：[decision_state_status.schema.json](services/execution_service/docs/decision_state_status.schema.json)
- pending / submitted / failed / skipped / decided / filled / canceled / rejected

### 10.2 状态写入来源字段（Service 行为）

Service 会把以下信息写入 decision_state（如可用）：

- execution_action / reject_reason
- attempts（来自 order_result.retry_meta.attempts）
- submitted_at_ms / last_error
- risk_state（从 signal_result.risk_state 解析）
- rule_debug（从 signal_result.rule_debug 解析）
- policy_snapshot
- trace_id（来自 DecisionIntent.trace_id 或 reconcile payload.trace_id）

实现：[app/service.py](services/execution_service/app/service.py#L144-L160) 与辅助提取函数（L451-L499）

---

## 11. Redis Key 与存储模式（汇总）

### 11.1 状态读取 keys（providers）

见：[redis_keys.md](services/execution_service/docs/redis_keys.md#L7-L86)

- execution:position:{exchange}:{account_id}:{symbol}
- execution:account:{exchange}:{account_id}
- execution:risk_policy:{exchange}:{symbol}

### 11.2 幂等 keys（idempotency_store）

见：[redis_keys.md](services/execution_service/docs/redis_keys.md#L87-L100)

- execution:idempotency:{decision_id}
- execution:idempotency:lock:{decision_id}
- reconcile 幂等 key：reconcile:{order_id}（存储在同一 idempotency_store 中）

### 11.3 状态机 keys（decision_state）

见：[redis_keys.md](services/execution_service/docs/redis_keys.md#L101-L112)

- execution:state:{decision_id}

### 11.4 confidence metrics keys

- Hash key（默认）：execution:metrics:confidence_migration

来源：[app/__init__.py](services/execution_service/app/__init__.py#L166-L190) 与 [confidence_metrics_store.py](services/execution_service/adapters/confidence_metrics_store.py#L48-L78)

---

## 12. 运行期环境变量（实现对齐）

### 12.1 Provider 模式

| 变量 | 默认值 | 含义 |
|---|---|---|
| EXECUTION_STATE_PROVIDER_MODE | redis | 仅支持 redis（读取 position/account/risk_policy） |
| EXECUTION_REDIS_URL | redis://127.0.0.1:6379/0 | Provider Redis URL |
| EXECUTION_POSITION_KEY_TEMPLATE | execution:position:{exchange}:{account_id}:{symbol} | 仓位 key 模板 |
| EXECUTION_ACCOUNT_KEY_TEMPLATE | execution:account:{exchange}:{account_id} | 账户 key 模板 |
| EXECUTION_RISK_POLICY_KEY_TEMPLATE | execution:risk_policy:{exchange}:{symbol} | 策略 key 模板 |

来源：[app/__init__.py](services/execution_service/app/__init__.py#L36-L62) 与 [redis_state_providers.py](services/execution_service/adapters/redis_state_providers.py#L57-L87)

### 12.2 执行下沉（submit）

| 变量 | 默认值 | 含义 |
|---|---|---|
| EXECUTION_SUBMIT_ENABLED | false | 是否启用 submit |
| EXECUTION_SINK_MODE | exchange | 默认 exchange（历史 mock 仅兼容模式） |
| EXECUTION_SINK_ENABLE_LEGACY_MOCK | false | 是否允许历史 `EXECUTION_SINK_MODE=mock` 兼容映射 |
| EXECUTION_SUBMIT_MAX_RETRIES | 0 | submit 重试次数 |
| EXECUTION_SUBMIT_BACKOFF_BASE_S | 0.2 | submit 退避基数 |

Exchange sink 关键变量（节选）：
- EXECUTION_SINK_EXCHANGE_VENUE（默认 binance）
- EXECUTION_SINK_EXCHANGE_DRY_RUN（默认 true）
- EXECUTION_SINK_EXCHANGE_API_BASE_URL（默认 https://api.binance.com）
- EXECUTION_SINK_EXCHANGE_API_KEY / API_SECRET（敏感信息，严禁日志输出）
- EXECUTION_SINK_EXCHANGE_RECV_WINDOW_MS / DEFAULT_ORDER_QTY / TIMEOUT_S

来源：[app/__init__.py](services/execution_service/app/__init__.py#L63-L102)

### 12.3 幂等

| 变量 | 默认值 | 含义 |
|---|---|---|
| EXECUTION_IDEMPOTENCY_ENABLED | true | 是否启用幂等 |
| EXECUTION_IDEMPOTENCY_MODE | memory | memory/redis |
| EXECUTION_IDEMPOTENCY_REDIS_URL | EXECUTION_REDIS_URL 或默认 | 幂等 Redis URL |
| EXECUTION_IDEMPOTENCY_KEY_TEMPLATE | execution:idempotency:{decision_id} | 缓存 key |
| EXECUTION_IDEMPOTENCY_TTL_S | 3600 | 缓存 TTL |
| EXECUTION_IDEMPOTENCY_LOCK_TTL_S | 30 | 锁 TTL |

来源：[app/__init__.py](services/execution_service/app/__init__.py#L103-L132)

### 12.4 状态机存储

| 变量 | 默认值 | 含义 |
|---|---|---|
| EXECUTION_STATE_MACHINE_ENABLED | true | 是否启用 decision_state |
| EXECUTION_STATE_MACHINE_MODE | memory | memory/redis |
| EXECUTION_STATE_MACHINE_REDIS_URL | EXECUTION_REDIS_URL 或默认 | state Redis URL |
| EXECUTION_STATE_MACHINE_KEY_TEMPLATE | execution:state:{decision_id} | state key |
| EXECUTION_STATE_MACHINE_TTL_S | 86400 | state TTL |

来源：[app/__init__.py](services/execution_service/app/__init__.py#L133-L165)

### 12.5 reconcile 重试

| 变量 | 默认值 | 含义 |
|---|---|---|
| EXECUTION_RECONCILE_MAX_RETRIES | 0 | 对账重试次数 |
| EXECUTION_RECONCILE_BACKOFF_BASE_S | 0.2 | 对账退避基数 |

来源：[app/__init__.py](services/execution_service/app/__init__.py#L191-L205) 与 [_reconcile_with_retry](services/execution_service/app/service.py#L283-L328)

### 12.6 confidence metrics

| 变量 | 默认值 | 含义 |
|---|---|---|
| EXECUTION_CONFIDENCE_METRICS_MODE | memory | memory/redis |
| EXECUTION_CONFIDENCE_METRICS_REDIS_URL | EXECUTION_REDIS_URL 或默认 | metrics Redis URL |
| EXECUTION_CONFIDENCE_METRICS_KEY | execution:metrics:confidence_migration | metrics key |
| EXECUTION_DEBUG_ALLOW_METRICS_RESET | false | 是否允许 reset 接口 |

来源：[app/__init__.py](services/execution_service/app/__init__.py#L166-L219) 与 [routes.py](services/execution_service/routes.py#L103-L110)

---

## 13. 与 agent_server_new 的对接（输入映射参考）

agent 侧会向 execution_service 发送 DecisionIntent。execution_service 仓库内也提供了一个“从 agent 执行计划映射到 DecisionIntent”的适配器，便于测试或脚本对齐：

- [agent_execution_plan_adapter.py](services/execution_service/adapters/agent_execution_plan_adapter.py)

其映射要点：
- direction：从 plan.direction 映射到 direction_intent（long/short/none）
- decision_confidence：优先使用 plan.decision_confidence，否则兼容回退 plan.confidence
- risk_hints：注入 agent_action_hint/agent_notes/decision_confidence（用于执行侧解释与下单推导）
