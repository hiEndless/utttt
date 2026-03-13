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
  - 显式路由优先级：`event_type_aliases` 归一化后 `event_type_routes` > `source_category_routes` > `rules.keywords` > `default_agent_key`
  - 业务 canonical 覆盖：`market_indicator_signal/onchain_wallet_anomaly/large_liquidation/social_news`
- LLM 旁路主判输入已增加“按 `decision_agent_key` 的证据裁剪”：
  - `technical/liquidation/onchain/social_news/generic` 使用不同的 active_events 与 key_features 过滤策略
  - 避免把无关噪声证据送入 LLM，降低跨事件类型误判
  - 同时注入 `decision_prompt(focus/checklist/avoid)`，使不同路由类型使用不同判定指令
  - `decision_prompt` 已配置化：`services/agent_server_new/config/signal_decision_prompt_profiles.json`，支持 `AGENT_SIGNAL_DECISION_PROMPT_CONFIG_FILE` 覆盖
- `bootstrap` 启动已接入 `SignalRouter` 配置校验门禁（生产环境配置非法直接拒绝启动）。
- `TradeEventWorkflow` 已输出 `SignalDecision`，并把 `decision_agent_key` 透传到 execution payload 的 `risk_hints`。
- `TradeEventWorkflow` 已透传 `prompt_config_source/prompt_config_version` 到 execution `risk_hints`，用于跨服务回放追踪提示词配置。
- `DecisionTrace` 已增加 `routing` 观测块，记录 `decision_agent_key/router_config_source/router_config_version/prompt_config_source/prompt_config_version`，用于回放时定位路由与提示词配置漂移。
- 当 `AGENT_LEGACY_PIPELINE_ENABLED=false` 时，workflow recorder 已退化为单节点 `workflow_bridge`（编排桥接记录），不再输出 `intent/rule/gate/planner` 业务节点记录。
- 当 `AGENT_LEGACY_PIPELINE_ENABLED=false` 时，不再加载 horizon policy 配置，避免 minimal 路径隐式依赖 legacy 风控初始化。
- 当 `AGENT_LEGACY_PIPELINE_ENABLED=false` 时，透传给 execution 的 `risk_hints.agent_action_hint` 由 `SignalDecision` 语义映射（`accept->add`，其余 `hold`），不再依赖 legacy `ExecutionPlan.action`。
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
- 已新增兼容开关：`AGENT_LEGACY_PIPELINE_ENABLED`（默认 `true`）。
  - `true`：维持旧 planner/gate 链路行为。
  - `false`：跳过 `Intent/Rule/Horizon/Strategy/Risk/ExecutionPlanner` 主链路，使用最小 `ExecutionPlan(hold)`，由 execution 侧做最终裁决。
  - `DecisionTrace.routing.pipeline_mode`：`legacy|minimal`，用于灰度对比统计。

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
