# market_state_engine 重构任务

## 结构状态边界收口（第一阶段）

- [x] Task 1: 收口 `MarketStateMSL` 契约，移除 `sentiment_state` 等外部事件语义槽位，仅保留结构状态字段。
- [x] Task 2: 同步更新 `engine/service` 输出实现，确保正常与短路分支均不再产出 `sentiment_state`。
- [x] Task 3: 同步更新下游解析（`agent_server_new`）以适配新的 MSL 结构契约。
- [x] Task 4: 增加并通过状态层回归测试，锁定 `msl` 中不再出现 `sentiment_state`。

## 输入域守卫（第二阶段）

- [x] Task 5: 在 `service.py` 增加输入域白名单守卫（拒绝或忽略 news/social/onchain 外部事件字段）。
- [x] Task 6: 新增边界测试，覆盖“混入外部事件字段”的处理策略。

## 引擎拆层（第三阶段）

- [x] Task 7: 将 `engine.py` 按因子拆分为 `regime/liquidity/positioning/volatility/risk/structure` 子模块。
- [x] Task 8: 维持输出契约不变，补充拆层后的回归测试。

## CI 契约守卫（第四阶段）

- [x] Task 9: 新增 `market_state_engine` 契约守卫脚本并接入 CI。
- [x] Task 10: 新增 `MSL` 字段白名单测试，锁定正常/短路分支输出字段集合。
- [x] Task 11: 更新守卫脚本，默认执行 `MSL` 白名单测试，防止契约字段漂移。
- [x] Task 12: 新增 `state->agent` 联动守卫脚本，联合检查状态层与决策层的 MSL 契约一致性。
- [x] Task 13: 新增新架构守卫总入口脚本，串联 feature/state/state->agent 全量守卫检查。

## 插件化状态推断（第五阶段）

- [x] Task 14: 新增 `state_inference` 插件基础协议（`InferenceResult/StateInferencePlugin`）与共享视图工具。
- [x] Task 15: 按能力拆分推断插件（`regime/positioning/volatility/liquidity/risk/structure`），替代集中式推断流程。
- [x] Task 16: 新增 `state_fusion` 编排器，按 `order` 执行插件并融合局部状态，统一收集插件警告。
- [x] Task 17: 新增 `msl_generator`，将融合状态映射为稳定 `MarketStateMSL` 契约输出。
- [x] Task 18: `engine.py` 接入插件引擎（`infer_msl_from_features`），并通过状态层与下游契约回归测试。
- [x] Task 19: 增加插件流水线回归测试，覆盖默认推断链路与插件异常降级（warning）分支。
- [x] Task 20: 更新 `scripts/check_market_state_engine_guard.sh`，将插件流水线测试纳入状态层契约守卫。
- [x] Task 21: 增加插件注册配置能力，支持 `enabled_plugins/disabled_plugins` 控制默认插件链路。
- [x] Task 22: `MarketStateEngine` 接收 `state_inference_config` 并将配置透传到插件推断引擎。
- [x] Task 23: `service.py` 支持通过环境变量加载插件启停配置（`MSE_STATE_PLUGINS_ENABLED/DISABLED`）。
- [x] Task 24: 补充插件配置回归测试（禁用插件与白名单启用模式）。
- [x] Task 25: 增加插件 `profile` 预设（`default/fast_mode/risk_only`）并接入推断引擎。
- [x] Task 26: 明确配置优先级规则（`enabled_plugins` 覆盖 `plugin_profile`，再应用 `disabled_plugins`）。
- [x] Task 27: `service.py` 支持 `MSE_STATE_PLUGIN_PROFILE` 环境变量。
- [x] Task 28: 增加 `profile` 回归测试（`fast_mode` 与优先级覆盖用例）。
- [x] Task 29: 增加服务层环境配置解析测试，覆盖 `MSE_STATE_PLUGIN_PROFILE/ENABLED/DISABLED` 读取行为。
- [x] Task 30: 新增 `config/state_inference_profiles.json`，将插件 profile 从代码内置下沉为配置文件。
- [x] Task 31: 状态推断引擎支持从 `profiles_file` 加载 profile，加载失败自动回退内置默认配置。
- [x] Task 32: `service.py` 新增 `MSE_STATE_PLUGIN_PROFILES_FILE` 环境变量透传配置文件路径。
- [x] Task 33: 增加自定义 profile 文件回归测试与环境变量解析回归测试。
- [x] Task 34: 将 `risk_only` profile 收敛为最小推断链路（`regime_inference + risk_inference`）。
- [x] Task 35: 增加 `risk_only` 语义回归测试，锁定“流动性/结构回退 unknown 且风险字段仍可输出”行为。
- [x] Task 36: 新增 `msl_generator_v1/v2` 多版本生成器，支持“不同 inference、同一 schema(v2)”。
- [x] Task 37: 新增生成器选择器与回退机制，未知版本自动回退 `msl_generator_v1`。
- [x] Task 38: 输出 `msl_meta` 元信息（`schema_version/inference_version/inference_profile`），并在短路分支给出固定元信息。
- [x] Task 39: `service.py` 支持 `MSE_MSL_INFERENCE_VERSION` 环境变量配置推断版本。
- [x] Task 40: 增加版本矩阵回归测试（v1/v2 同 schema、unknown 版本回退、服务层元信息输出）。
- [x] Task 41: 在 `MarketStateEngine` 增加多周期 `msl_bundle` 生成能力（`short_term/mid_term/long_term`）。
- [x] Task 42: 增加 `cross_horizon` 聚合器，输出周期一致性与冲突明细（至少含 `trend` 冲突）。
- [x] Task 43: `service.py` 正式输出 `msl_bundle/msl_bundle_meta/cross_horizon`，并保留原 `msl` 兼容字段。
- [x] Task 44: 增加多周期回归测试（short bullish vs long bearish 冲突场景）。
- [x] Task 45: 扩展 `cross_horizon` 冲突字段到 `phase/volatility_regime/liquidity_risk`。
- [x] Task 46: 冻结冲突优先级规则（`trend > phase > volatility_regime > liquidity_risk`）并补充回归测试。
- [x] Task 47: 为 `cross_horizon` 增加执行建议输出（`suggested_policy/policy_reason`）。
- [x] Task 48: 冻结建议规则：`conflicting->wait_confirmation/reduce_risk`、`mixed->reduce_risk`、`aligned->follow_long_term`、`unknown->no_action`。
- [x] Task 49: 补充策略建议回归测试（冲突场景与对齐场景）并覆盖短路分支默认值。
- [x] Task 50: `agent_server_new` 的 market_state 端口与 HTTP adapter 透传 `msl_meta/msl_bundle/cross_horizon`。
- [x] Task 51: `ContextBuilder` 注入 `cross_horizon/msl_meta` 到 `key_market_features`，供下游决策直接消费。
- [x] Task 52: 新增 `state->agent` 下游契约测试，锁定 `suggested_policy` 消费路径并接入守卫脚本。
- [x] Task 53: 在 `TradeEventWorkflow` 增加 `horizon_policy_gate`，于 `strategy_gate` 前消费 `cross_horizon.suggested_policy`。
- [x] Task 54: 冻结门控规则：`wait_confirmation/reduce_risk + increase intent -> skip`，其余策略不阻断。
- [x] Task 55: 增加 workflow 回归测试（`wait_confirmation -> skip`、`follow_long_term -> allow`）并接入 `state->agent` 守卫。
- [x] Task 56: 将 `horizon_policy_gate` 从 workflow 内联逻辑抽离到 `agent_server_new/domain/horizon_policy_gate.py`。
- [x] Task 57: 增加 `horizon_policy_gate` 领域单测（阻断与放行规则）。
- [x] Task 58: 更新 `state->agent` 守卫脚本，纳入 `horizon_policy_gate` 与 workflow 门控回归测试。
- [x] Task 59: 将 `horizon_policy_gate` 规则改为配置驱动（`block_on_increase_policies`），替代硬编码阻断集合。
- [x] Task 60: `TradeEventWorkflow` 支持注入 `horizon_policy_config`，并透传到 `horizon_policy_gate`。
- [x] Task 61: 增加配置化门控回归测试（自定义配置关闭 `wait_confirmation` 阻断）。
- [x] Task 62: `horizon_policy_gate` 支持统一环境变量加载（`AGENT_HORIZON_POLICY_BLOCK_ON_INCREASE`、`AGENT_HORIZON_POLICY_CONFIG_JSON`）。
- [x] Task 63: `TradeEventWorkflow` 在未传入显式配置时默认加载环境变量配置。
- [x] Task 64: 增加环境变量配置回归测试（CSV/JSON 解析与 workflow 自动加载）。
- [x] Task 65: 新增 `agent_server_new/.env.example`，沉淀 `HorizonPolicyGate` 环境变量样例，降低部署遗漏风险。
- [x] Task 66: 扩展 `.env.example`，补充 `market_state_engine` provider 连接参数（base_url/timeout）。
- [x] Task 67: `HttpMarketStateProvider` 增加 `from_env()`，支持统一环境变量构造。
- [x] Task 68: 增加 `from_env` 回归测试并同步 README 运行配置说明。
- [x] Task 69: 新增 `agent_server_new/app/bootstrap.py`，提供 `create_trade_event_workflow_from_env()` 默认装配入口。
- [x] Task 70: 增加 bootstrap 回归测试，锁定默认 adapter 接线与环境变量生效。
- [x] Task 71: 更新 `state->agent` 守卫脚本与 `services/agent_server_new/README.md`，冻结 bootstrap 使用方式。
- [x] Task 72: 新增 `agent_server_new/runner.py`（`python -m agent_server_new.runner`）作为最小 CLI 运行入口。
- [x] Task 73: 增加 runner 回归测试（`--dry-run` 与单次执行分支）。
- [x] Task 74: 更新守卫脚本与 README，冻结 CLI smoke test 使用方式。
- [x] Task 75: 修复 `signal_evaluator` 对旧 MSL 字段的依赖，切换到当前契约字段（`liquidity/positioning/anomalies`）。
- [x] Task 76: 新增 `agent_server_new/pipeline_smoke.py`，提供单进程 one-shot pipeline 冒烟入口。
- [x] Task 77: 增加 pipeline smoke 回归测试并接入 `state->agent` 守卫脚本。
- [x] Task 78: 修复 `intent_resolver/strategy_gate/rule_planner` 的旧 MSL 字段访问，统一切换到当前契约字段。
- [x] Task 79: 通过 one-shot pipeline 测试锁定“真实 workflow 不依赖旧字段也可跑通”。
- [x] Task 80: 在 `agent_server_new/docs` 新增完整重构方案文档（V2），冻结职责收敛与迁移阶段。
- [x] Task 81: 创建 `execution_service` 目录骨架（README/TASKS/docs/ports/app/domain/adapters/text）。
- [x] Task 82: 补充 execution 层 API/边界/迁移文档，形成下游服务文档入口。
- [x] Task 83: 同步项目总览文档（`ARCHITECTURE_NEW.md`、`CONTRACTS_QUICK_REF.md`、`services/agent_server_new/README.md`）避免入口过时。
- [x] Task 84: 冻结“agent 裁决链移除 Position Context”文档决议，并同步到 agent/architecture/contracts 文档入口。
- [x] Task 85: 在入口文档增加“当前实现链路 vs 目标收敛链路”业务流程分析，明确 event_center_new 位置与 execution 权责边界。
- [x] Task 86: 新增跨模块迁移执行清单（Playbook），并把入口链接同步到总览与契约速查文档。
- [x] Task 87: 落地 execution_service Task 1，冻结 `DecisionIntent v1` 输入契约并同步 API/README/TASKS 文档。
- [x] Task 88: 落地 execution_service Task 2，冻结 `ExecutionResult v1` 输出契约并同步 API/README/TASKS 文档。
- [x] Task 89: 落地 execution_service Task 3，新增 `AccountStateProvider` 端口与最小 stub providers，并补测试与文档同步。
- [x] Task 90: 落地 execution_service Task 4，实现确定性执行裁决器并锁定规则优先级测试。
- [x] Task 91: 落地 execution_service Task 5，新增最小 HTTP API（healthz/decide）并补接口测试。
- [x] Task 92: 落地 execution_service Task 6，新增 agent->execution 适配器与最小联调冒烟测试。
- [x] Task 93: 落地 execution_service Task 7，新增 agent->execution 守卫脚本并接入新架构总守卫入口。
- [x] Task 94: 在 agent_server_new 接入可选 execution HTTP decider（环境开关），并补 workflow 调用测试与文档同步。
- [x] Task 95: 修复 execution decider 接线时序回归（plan 未定义），并通过 state->agent 与全量守卫复验。
- [x] Task 96: execution_service 新增 Redis 状态 providers 与运行模式切换（stub/redis），并同步文档与测试。
- [x] Task 97: 修复 execution_service app 导入冲突（app.py 与 app/ 包同名）并通过全量守卫复验。
- [x] Task 98: 扩展 agent->execution 守卫覆盖 Redis/providers 模式测试。
- [x] Task 99: agent workflow 新增 `run_with_result()` 输出 execution 最终裁决对象（兼容保留 run 返回 plan）。
- [x] Task 100: 新增 execution_service Redis 集成测试（binance/ETHUSDT）并同步 README/TASKS。
- [x] Task 101: runner/pipeline_smoke 新增 `--use-execution-result` 输出模式并补测试。
- [x] Task 102: execution_service Redis key 契约文档落地并同步架构入口文档。
- [x] Task 103: runner 新增 `--print-json` 输出模式，便于下游脚本直接消费。
- [x] Task 104: execution_service 新增 debug 状态快照接口并补测试与文档。
- [x] Task 105: runner 新增 `--fail-on-execution-reject` 退出码控制，便于自动化编排失败快照。
- [x] Task 106: execution_service debug 接口支持 `redact` 脱敏查询参数并补测试。
- [x] Task 107: execution_service 新增 `/version` 契约版本接口并同步 API/README。
- [x] Task 108: 冻结 runner `--print-json` 输出契约文档（含退出码语义）并挂入口。
- [x] Task 109: runner 输出契约补充 `jq/Python` 解析示例，降低下游接入成本。
- [x] Task 110: `check_agent_to_execution_guard.sh` 纳入 execution API（含 `/version`）测试。
- [x] Task 111: 新增 runner JSON Schema 文件与轻量校验测试，并接入 state->agent 守卫。
- [x] Task 112: 新增 execution_service cURL 示例文档并同步架构/契约入口链接。
- [x] Task 113: 入口文档新增 runner JSON Schema 链接，明确机器可校验契约入口。
- [x] Task 114: 新增 execution_service HTTPie 示例文档并同步架构/契约入口链接。
- [x] Task 115: 新增 `docs/CONTRACT_INDEX.md` 契约索引并同步入口文档链接。
- [x] Task 116: 新增 `check_runner_output_schema_guard.sh` 并接入全量守卫入口。
- [x] Task 117: 入口文档顶部统一指向 `CONTRACT_INDEX.md` 作为唯一契约入口。
- [x] Task 118: 新增 `check_contract_docs_index_guard.sh` 并接入全量守卫入口。
- [x] Task 119: 增强 contract docs index 守卫，检查 `ARCHITECTURE_NEW/CONTRACTS_QUICK_REF` 显式引用 `CONTRACT_INDEX.md`。
- [x] Task 120: execution_service 接入可选 ExecutionSink 下沉流程（mock）并补提交成功/失败回归测试。
- [x] Task 121: execution_service 接入 `decision_id` 幂等缓存（memory/redis）并补重复 submit 防重回归测试。
- [x] Task 122: execution_service 接入 `decision_id` 处理锁（lock TTL），并补并发防重行为回归测试。
- [x] Task 123: execution_service 接入执行状态机存储（memory/redis），并在 debug 接口支持按 `decision_id` 查询状态。
- [x] Task 124: execution_service submit 下沉支持重试（指数退避 + 最大次数）并输出 retry_meta。
- [x] Task 125: `market_state_engine` 新增 `SelectedEventProvider` 端口与 Redis 适配器，服务层支持可选融合 selected_event（失败降级不抛错），并补回归测试与 README 同步。
