# agent_server_new 重构方案（V2）

更新时间：2026-03-13

## 1. 目标

将 `agent_server_new` 收敛为“单 agent 判定层”：

1. 使用 LLM 基于结构化输入（MSL + 事件证据）判断信号方向是否可信。
2. 按信号类型路由到对应的信号决策 agent。
3. 不在 agent 层执行任何仓位/风控/动作阻断。
4. 风控与最终动作裁决全部下沉到 `execution_service`。

一句话定义：

> agent 只回答“这个信号是否可信”，execution 才回答“是否允许执行以及如何执行”。

## 2. 目标架构

```text
event_center_new(selected_event/active_events)
  + market_state_engine(msl + key_features)
    -> agent_server_new(signal routing + signal decision)
      -> execution_service(final risk + final action)
```

触发方式（当前冻结）：

1. 主链路：`event_center_new(signal_event)` -> `agent_server_new`
2. 辅链路：`state_refresh_event` -> `agent_server_new`（巡检/补漏）

## 3. 输入与路由冻结

统一输入结构：

`MSL -> Key Evidence -> Active Events -> Signal Event`

说明：

1. `MSL`：降噪后的市场语义主语境。
2. `Signal Event`：触发事件本体（主判对象）。
3. `Active Events`：背景事件（news/social/onchain/liquidation/technical 等）。
4. `Position Context`：不进入 agent，完全由 `execution_service` 消费。

事件来源约束：

1. 外部事件（news/social/onchain）不直接绕过事件中心。
2. 外部事件与结构事件统一经 `event_center_new` 归一后输入 agent（`ec:selected`）。

## 4. 单 agent 路由模型

本层采用“单入口 + 事件类型路由”的多策略单 agent 架构：

1. 入口：`SignalRouter`
- 输入：`signal_event.type/source_category`
- 输出：`agent_key`

2. 决策器：`SignalDecisionAgent`
- 接口统一：`decide(context) -> SignalDecision`
- 内部按 `agent_key` 选择对应提示词、证据裁剪和判定策略

建议初始路由分类：

1. `technical`（指标/结构类信号）
2. `liquidation`（大额清算/流动性冲击）
3. `onchain`（链上钱包/资金流异动）
4. `social_news`（社媒/新闻/宏观语义事件）
5. `generic`（兜底）

## 5. agent 输出契约（收敛方向）

agent 只输出语义裁决对象 `SignalDecision`，不输出执行动作：

1. `decision_id`
2. `exchange`
3. `symbol`
4. `signal_direction`
5. `signal_verdict`（`accept|reject|uncertain`）
6. `confidence`
7. `reliability_score`
8. `reasons`
9. `evidence_refs`
10. `llm_observation`

显式禁止在 agent 输出中出现：

1. `allow_open/allow_add/allow_reduce/allow_exit`
2. `risk_constraints`
3. `sizing`
4. `execution_action`
5. `reject_reason`

## 6. execution_service 职责冻结

`execution_service` 成为唯一硬约束与最终动作权威：

1. 仓位上限/加减仓约束
2. 账户风险/PnL/冷却等风控规则
3. 最终动作裁决（`add/reduce/hold/exit/skip`）
4. 下单与回执/对账语义

## 7. workflow 角色重定义

后续 `workflow` 仅用于编排，不承载决策语义：

1. 决策结果入库（trace/event store）
2. 事后验证（上一轮决策正确性回放）
3. 统计评估（命中率/不确定率/偏差对账）

若以上需求关闭，可退化为“路由 + 决策”轻执行路径。

## 8. 分阶段实施计划

1. Phase A（契约阶段）
- 新增并冻结 `SignalDecision` 契约。
- `agent -> execution` 改为传递语义裁决对象。
- 文档明确“agent 无风控字段”禁令。

2. Phase B（实现阶段）
- `SignalRouter` 落地，按事件类型路由到不同 signal decision agent。
- `SignalEvaluator` 升级为 LLM 主判（MSL 驱动）。
- `RulePlanner/RiskGate/ExecutionPlanner` 从主链路移除。

当前进展补充：
- `SignalRouter` 已在代码中落地（`technical/liquidation/onchain/social_news/generic`）。
- `SignalRouter` 已支持配置驱动映射：
  - 默认配置文件：`services/agent_server_new/config/signal_router_profiles.json`
  - 环境变量覆盖：`AGENT_SIGNAL_ROUTER_CONFIG_FILE`
  - 事件类型提取优先级：`selected_type` > `selected_event_type` > `event_type` > `type` > `kind` > `signal_type`
  - 来源类型提取优先级：`source_category` > `event_source_category` > `signal_source_type` > `source_type` > `source_signal_type` > `source.category`
  - 显式路由优先级：`event_type_aliases` 归一化后 `event_type_routes` > `source_category_routes` > `rules.keywords` > `default_agent_key`
  - 业务 canonical 覆盖：`market_indicator_signal/onchain_wallet_anomaly/large_liquidation/social_news`
  - 业务别名基线已扩展（指标/链上钱包异动/大额清算/社媒新闻），例如 `chain_wallet_anomaly/market_large_liquidation/social_media_hot_news`，作为上游事件命名波动的稳定收敛层。
- 已新增入口边界守卫测试：`event_center_new -> agent_server_new` 常见事件类型必须命中 canonical/alias 路由基线，避免 silently 回落 `generic`。
- LLM 旁路主判输入已增加“按 `decision_agent_key` 的证据裁剪”：
  - `technical/liquidation/onchain/social_news/generic` 使用不同的 active_events 与 key_features 过滤策略
  - 避免把无关噪声证据送入 LLM，降低跨事件类型误判
  - 同时注入 `decision_prompt(focus/checklist/avoid/model_id?)`，使不同路由类型使用不同判定指令，并可按路由覆盖 LLM 模型
  - `decision_prompt` 已配置化：`services/agent_server_new/config/signal_decision_prompt_profiles.json`，支持 `AGENT_SIGNAL_DECISION_PROMPT_CONFIG_FILE` 覆盖
- `bootstrap` 启动已接入 `SignalRouter` 配置校验门禁（生产环境配置非法直接拒绝启动）。
- `TradeEventWorkflow` 已输出 `SignalDecision`，并把 `decision_agent_key` 透传到 execution payload 的 `risk_hints`。
- `TradeEventWorkflow` 已透传 `prompt_config_source/prompt_config_version` 到 execution `risk_hints`，用于跨服务回放追踪提示词配置。
- `DecisionTrace` 已增加 `routing` 观测块，记录 `decision_agent_key/router_config_source/router_config_version/prompt_config_source/prompt_config_version/event_type_raw/event_type_normalized/event_type_match_mode`，用于回放时定位路由与提示词配置漂移。
- workflow 已统一“先路由后判定”：同一个 `decision_agent_key` 同时用于 LLM 观测上下文与 `SignalDecisionAgent.decide`，避免重复路由造成潜在漂移。
- workflow 已新增 `pipeline_compat_state` 兼容层适配（集中 legacy gate 中间态），主干聚焦 `signal_decision -> decision_intent_payload -> execution_decider`，为后续下线 legacy 分支做结构准备。
- 兼容层实现已下沉到 `services/agent_server_new/domain/pipeline_compat_adapter.py`，workflow 不再内联 gate 组合细节。
- legacy 阶段录制输出（intent/rule/horizon/strategy/execution_planner）也已由适配器统一组装，workflow 仅负责写出。
- decision_trace 的 legacy 专属片段（intent/rule_plan/strategy_gate_result/risk_gate）已改由适配器组装，workflow 只保留 trace 外壳拼装。
- symbol memory 写入中的 legacy 片段（cross_horizon_policy/intent/plan）已下沉适配器，workflow 仅透传组装结果。
- execution_decider 请求体（含 `risk_hints` 与 minimal/legacy 判定差异）已下沉适配器，workflow 仅负责参数透传与调用。
- `workflow_bridge` payload 已下沉适配器统一组装，workflow 只负责阶段输出写入。
- `SignalDecision` 归一化构建已下沉适配器，workflow 不再内联裁决对象组装规则。
- `decision_trace` 外壳 payload 组装已下沉适配器，workflow 仅负责参数透传与 schema 校验/写出。
- recorder 阶段输出已统一为适配器的 `stage->payload` 映射，workflow 仅循环写出并保留 schema guard。
- 已增加阶段输出冻结守卫：`verification/auditors/agent_server_new/test_pipeline_stage_output_guard.py`，防止新增 legacy 专属输出键。
- symbol memory 记录 payload 也已下沉适配器统一组装，workflow 仅负责 recorder 调用。
- legacy 兼容开关已移除，workflow 固定为 minimal 语义链路。
- workflow recorder 固定输出 `workflow_bridge`（编排桥接记录）与 `decision_trace`，不再输出 `intent/rule/gate/planner` 业务节点记录。
- 透传给 execution 的 `risk_hints.agent_action_hint` 由 `SignalDecision` 语义映射（`accept->add`，其余 `hold`）。
- `decision_confidence` 与 `risk_hints.decision_confidence` 来自 `SignalDecision.confidence`，并标记 `decision_confidence_source=agent_signal_decision`。
- `WorkflowResult.agent_plan` 与信号语义计划保持一致；最终风控与动作以 execution 结果为准。
- 主判入口已抽象为 `SignalDecisionAgent`（当前默认实现为 `RoutedRuleBasedSignalDecisionAgent`），workflow 不再直接调用 `evaluate_signal`，为后续替换 LLM 判定实现留出无侵入插槽。
- 当启用 `llm_observer` 时，默认主判实现已切换为 `RoutedHybridSignalDecisionAgent`：优先消费 LLM 判定，解析失败自动 `rule_fallback`；并透传 `decision_mode(llm|rule_fallback|rule)` 到 execution `risk_hints`。
- `DecisionTrace.routing` 已补充 `decision_mode/llm_parse_status`，用于回放时快速区分“LLM 直接判定”与“LLM 失败回退规则”的链路占比。
- `DecisionTrace.routing` 已补充 `llm_contract_error_code/llm_contract_errors`，用于细分 `llm_invalid_payload` 的失败类型并支持离线统计。
  - `llm_contract_error_code` 已收敛为标准枚举（`llm_raw_content_missing/llm_json_parse_error/llm_json_not_object/llm_schema_validation_failed/llm_confidence_parse_error`）。
  - `llm_contract_errors` 限制最多 8 条，避免 trace 膨胀。
- `RoutedHybridSignalDecisionAgent` 已启用严格 LLM 输出契约校验（JSON 对象 + 白名单字段 + 枚举/范围/类型校验），不合法 payload 统一回落 `rule_fallback`。
  - 契约文件：`services/agent_server_new/docs/llm_signal_decision.schema.json`

3. Phase C（兼容阶段）
- 保留旧 `TradeEventWorkflow` 作为兼容壳，仅做转发，不再执行业务风控。
- 完成 CLI/API 无破坏迁移。
- 已完成兼容层下线：不再提供 legacy/minimal 双态切换。
- `DecisionTrace.routing.pipeline_mode` 固定为 `minimal`，用于观测链路完整性。

4. Phase D（收口阶段）
- 删除 agent 内风控/动作阻断遗留逻辑。
- execution 成为唯一最终动作裁决路径。
- 下线旧字段与兼容分支。

## 9. 验收标准

1. agent 输出只包含 `SignalDecision` 语义字段，无风控执行字段。
2. 任意输入下，最终动作仅由 `execution_service` 给出。
3. `news/social/onchain` 与结构事件统一经 `event_center_new` 输入 agent。
4. 路由后不同类型信号均可稳定产出 `accept/reject/uncertain`。
5. `DecisionTrace` 可复盘并可用于事后正确性验证。
