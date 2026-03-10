# execution_service Migration

## 当前状态

当前仓库已完成：

1. `agent_server_new` 决策链路收敛
2. `market_state_engine` 输出稳定状态契约
3. execution_service 目录与文档骨架建立

## 下一步迁移

1. 把仓位硬风控规则从 agent 迁移到 execution_service（进行中）
2. 统一拒绝原因码（已冻结首批）
3. 建立 agent -> execution 契约测试（进行中）
4. 接入真实执行与回执链路

## 当前已落地

1. `DecisionIntent v1` 与 `ExecutionResult v1` 已冻结
2. `position/account` provider 端口已定义，并提供最小 stub
3. 确定性执行裁决器已落地，规则优先级固定为：
   - 仓位上限
   - 冷却期
   - 回撤阈值
   - 方向冲突
4. 已有最小 `agent -> execution` 适配与冒烟测试（ExecutionPlan -> DecisionIntent）
5. 已新增 `scripts/check_agent_to_execution_guard.sh` 并接入 `check_new_arch_guards.sh`
6. execution_service 已支持 `stub/redis` 双模式状态提供器，可逐步替换到真实 Redis 数据
7. execution_service 已支持可选 `ExecutionSink` 下沉流程（当前 `mock`），并在失败时做业务降级回退
8. execution_service 已支持基于 `decision_id` 的幂等缓存（memory/redis），避免重复提交
9. execution_service 已支持 `decision_id` 处理锁（lock TTL），并发重复请求可返回 `idempotency_in_progress`
10. execution_service 已支持执行状态机存储（memory/redis），可追踪 `pending/submitted/failed/skipped/decided`
11. execution_service submit 已支持重试（指数退避 + 最大次数），并将重试轨迹写入 `order_result.retry_meta`
12. execution_state debug 快照已扩展 `attempts/submitted_at_ms/last_error/last_transition`，便于联调排障
13. execution_state 已增加状态跃迁合法性校验，终态不会被非法回跳覆盖
14. execution_state 已透传 `trace_id` 并写入 `source=execution_service`，支持跨服务链路定位
15. execution_state 已冻结独立 schema（`decision_state.schema.json`）并接入守卫脚本防漂移
16. ExecutionResult 已冻结独立 schema（`execution_result.schema.json`）并接入守卫脚本防漂移
17. DecisionIntent 已冻结独立 schema（`decision_intent.schema.json`）并接入守卫脚本防漂移
18. execution 三份 schema 已统一纳入 `docs/CONTRACT_INDEX.md` 作为项目级单入口索引
19. execution 模块内 cURL/HTTPie 文档已补齐 schema 快速定位段，和项目入口文档保持一致
20. execution API 文档已补充“schema 与字段来源映射表”，支持联调与评审快速追溯
21. execution 已新增机器可校验 `schema_mapping.json`，并接入守卫防止表格/代码映射漂移
22. execution `/version` 已透出 `schema_mapping_version`，并通过测试强校验与 mapping 文件版本一致
23. schema_mapping 已新增 `owner/change_policy` 元数据，并由测试强校验变更责任与升级策略
24. 新增 execution 合同入口守卫，要求 `CONTRACT_INDEX` 显式声明并对齐 schema mapping 版本
25. schema_mapping 已新增 `last_updated`，并由入口守卫校验不晚于 CONTRACT_INDEX 更新时间
26. 已收紧 `last_updated` 规则：必须严格等于 CONTRACT_INDEX 更新时间，避免发布时序漂移
27. 已新增 breaking 升版守卫：`change_policy=breaking` 变更时必须提升 mapping 主版本
28. breaking 升版守卫已扩展到 schema 文件内容 hash 变化，避免仅改 schema 文件导致漏检
29. breaking 升版守卫已输出触发对象与原因，便于 CI 失败快速定位
30. execution 已新增 `POST /internal/execution/reconcile` 回执对账接口，支持 `mock/exchange_skeleton` sink
31. reconcile 已支持写回 execution_state 终态（`filled/canceled/rejected`）并纳入状态机跃迁约束
32. reconcile 响应契约已冻结为独立 schema，并接入守卫与项目文档索引
33. reconcile 已接入 `order_id` 维度幂等（缓存+锁），避免重复写回覆盖状态
34. reconcile 已支持错误分级重试（指数退避），并在响应中输出 `retry_meta`
35. reconcile 失败已标准化为业务响应（`status=failed`），降低下游 502 分支复杂度
36. reconcile 错误码字段已统一为 `reason_code`，并覆盖 `reconcile_in_progress` 场景
37. reconcile `reason_code` 已抽为代码常量，并由测试强校验与 schema 枚举一致
38. reconcile `status` 已抽为代码常量，并由测试强校验与 schema 枚举一致
39. submit/reconcile `retry_meta.status` 已抽为共享常量，并由测试强校验两份 schema 枚举一致
40. ExecutionResult schema 发生破坏性变更后，`schema_mapping_version` 已按守卫要求升级到 `execution-schema-mapping-v3`
41. 已新增独立 `retry_meta` schema，并接入守卫与项目索引文档
42. `execution_result/execution_reconcile_result` 的 `retry_meta` 已改为 `$ref` 引用独立 schema，并更新 schema 测试支持本地 `$ref` 解析
43. `retry_meta` 契约一致性测试已升级为按 `$ref` 读取独立 schema，避免内联路径依赖
44. 已抽取统一 schema 校验工具，减少 execution 契约测试重复逻辑并避免后续漏改
45. `schema_mapping.json` 已显式登记 `RetryMeta` 与 `$ref` 引用来源，并通过测试强校验引用路径与期望值
46. `schema_mapping.references` 已支持结构化 JSON 值校验（非仅字符串），并新增 `DecisionState` 关键字段（`status/source`）断言
47. `DecisionIntent/ExecutionResult` 已补齐关键引用断言（方向/置信度/动作/拒绝码/retry_meta `$ref`），提升 breaking 契约防漂移能力
48. `ExecutionReconcileResult` 已纳入 `schema_mapping`，并冻结 `status/reason_code/retry_meta` 关键断言
49. `ExchangeExecutionSink` 已支持可配置 `dry_run` 与 Binance 签名请求骨架，并新增单测覆盖下单参数构建逻辑
50. `ExchangeExecutionSink.reconcile` 已支持 Binance 原始状态到标准状态映射，并返回 `exchange_status_raw` 便于联调排障
51. `ExchangeExecutionSink.reconcile` 已补齐 `avg_price` 多源回退计算，降低市价单回执均价缺失概率
52. execution 已引入 `account_id` 作用域（默认 `main`），并贯通到 position/account provider 与 debug 接口，兼容后续多账户扩展
53. 风控规则已支持 `hedge` 双向持仓：同 symbol 多空腿独立限额（`max_long/max_short_position_size`）并保持 `one_way` 兼容
54. execution 输出已新增 `signal_result`（模拟信号结构），可直接供下游消费而不依赖真实交易下沉
55. `signal_result` 已冻结为独立 schema 并纳入守卫/索引；因 `ExecutionResult` 契约 breaking 变更，schema mapping 已升版至 `v4`
56. `account_id` 已正式纳入 `DecisionIntent` 契约与 schema/mapping，schema mapping 版本已升至 `v5`
57. `account_id` 已贯通到 `decision_state` 与 `reconcile` 写回链路，调试快照可按账户维度稳定追踪
58. `signal_result` 已增加结构化 `risk_checks`，优先输出账户风控（回撤/余额）并附带 symbol 暴露与腿级限额检查
59. `risk_policy` 已冻结独立 schema，并接入守卫与 provider 默认值测试，策略字段定义统一收敛
60. `risk_checks.check` 已收敛为常量枚举，并新增代码-契约一致性测试防止 schema/实现漂移
61. `risk_checks.message_zh` 已冻结为必填中文说明字段，确保风控检查项具备可读诊断信息
62. `risk_checks.scope/status` 已收敛为常量枚举，并新增代码-契约一致性测试防止 schema/实现漂移
63. `risk_checks.message_zh` 文案模板已收敛为常量并新增模板稳定性测试，减少多处拼接导致的格式漂移
64. `risk_checks` 构造逻辑已拆分为独立 builder 模块并新增单测，降低 `risk_rules` 复杂度并提升可维护性
65. `risk_check_builder` 已新增逐项 schema 契约校验测试，确保 builder 产物持续满足 `execution_signal_result` 规范
66. 裁决结果组装逻辑已拆分为独立 result builder，并纳入单测与守卫，`risk_rules` 仅保留规则判定职责
67. `schema_mapping` 中 `ExecutionSignalResult` 的代码锚点已切换到 `risk_result_builder`，与最新实现保持一致
68. 风控判定改为规则表驱动并冻结默认优先级；新增 `risk_policy.rule_priority_order` 可选覆盖（无效配置回退默认）
69. 新增账户级组合风控阈值（`max_account_notional`/`max_margin_ratio`），并贯通到规则拒绝与 `risk_checks` 输出
70. 新增账户亏损风控阈值（`max_daily_loss`/`max_consecutive_loss_count`），并贯通到规则拒绝与 `risk_checks` 输出
71. `signal_result` 已新增 `rule_debug` 调试字段，输出命中规则名、规则顺序和命中值/阈值，便于联调排障
72. `rule_debug` 已回写到 `decision_state`，可通过 debug state + `decision_id` 回看最近一次命中规则链路
73. `rule_debug` 已增加 `matched_at_ms` 命中时间戳，支持跨服务链路的时序对齐与回放分析
74. `rule_debug` 已增加 `evaluation_trace`，支持按规则优先级回放每条规则的 pass/fail 与值阈值轨迹
75. `evaluation_trace` 已增加 `note_zh`，每条规则评估均输出中文说明，提升值班排障效率
76. `evaluation_trace` 已增加 `scope`（account/symbol/position），可快速定位命中维度
77. `evaluation_trace` 已增加 `order` 顺序索引，支持按规则顺序稳定回放与定位
78. 引入标准化 `risk_state`（`normal|warn|reduce_only|frozen`），并贯通到 `signal_result` 与 `decision_state`
79. `risk_state` 已增加前态记忆与降级防抖（`frozen/reduce_only` 不会单拍直接回落 `normal`），并在 provider 中持久化读取
80. Redis 账户 provider 已对 `risk_state` 进行枚举归一化，非法值自动回退 `normal`
81. Stub 账户 provider 已对 `risk_state` 进行同策略归一化，保证 stub/redis 模式一致
82. `rule_debug` 已增加 `previous_risk_state/current_risk_state`，支持风险状态迁移审计与回放
83. `rule_debug` 已增加 `risk_state_changed` 布尔字段，支持快速筛选风险态迁移事件
84. `rule_debug` 已增加 `risk_state_change_reason` 标准原因码，支持风险态迁移可解释回放
85. `rule_debug` 已增加 `risk_state_change_reason_zh` 中文解释字段，便于日志与告警直接展示
86. `risk_state_change_reason` 及中文解释已收敛到单点常量模块，并新增常量-契约一致性测试
87. `risk_state` 四态已收敛到单点常量模块，并新增常量-契约一致性测试
88. `risk_state_change_reason(_zh)` 已抽取独立 schema 并通过 `$ref` 复用，减少 signal/decision 契约重复定义
89. 本地 schema 校验工具已支持带 JSON Pointer 的 `$ref`（`#/properties/...`），可稳定校验子 schema 复用
90. `risk_state`（含 `previous/current_risk_state`）已抽取独立 schema 并通过 `$ref` 复用，减少 signal/decision 契约重复定义
91. `rule_debug` 已抽取独立 schema 并通过 `$ref` 复用，减少 signal/decision 契约重复定义
92. `evaluation_trace` 已抽取独立 schema 并通过 `$ref` 复用，减少 `rule_debug` 契约重复定义
93. `scope/position_before/position_after_simulation` 已抽取独立 schema 并通过 `$ref` 复用，减少 `execution_signal_result` 契约重复定义
94. `signal_action` 已抽取独立 schema 并通过 `$ref` 复用，减少 `execution_signal_result` 契约重复定义
95. `risk_checks` 已抽取独立 schema 并通过 `$ref` 复用，减少 `execution_signal_result` 契约重复定义
96. `mode` 已抽取独立 schema 并通过 `$ref` 复用，减少 `execution_signal_result` 契约重复定义
97. `rule_priority_order` 已抽取独立 schema 并通过 `$ref` 复用，减少 `risk_policy/rule_debug` 契约重复定义
98. `position_mode` 已抽取独立 schema 并通过 `$ref` 复用，减少 `risk_policy/position_before` 契约重复定义
99. `decision_state.status/last_transition` 已抽取独立 schema 并通过 `$ref` 复用，减少状态契约重复定义
100. `execution_result/decision_state.execution_action` 已抽取独立 schema 并通过 `$ref` 复用，减少动作枚举重复定义
101. `execution_result/decision_state.reject_reason` 已抽取独立 schema 并通过 `$ref` 复用，减少拒绝原因重复定义
102. 因 `ExecutionResult` schema 内容变更触发 breaking 守卫，`schema_mapping_version` 已升版到 `execution-schema-mapping-v8`

## 关键收敛决议（冻结）

1. `Position Context` 由 execution_service 侧读取与使用
2. agent 不再以 `Position Context` 作为裁决输入
3. execution_service 成为最终动作裁决权威（add/reduce/hold/exit/skip）
