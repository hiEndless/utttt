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

当前进展补充（已完成能力矩阵）：

| 能力域 | 已完成能力 | 关键锚点 |
|---|---|---|
| 路由与输入归一 | `SignalRouter` 落地；事件类型/来源类型优先级与 alias/canonical 路由生效 | `signal_router_profiles.json`、`test_signal_router_event_type_boundary_guard.py` |
| LLM 判定与降噪 | 路由驱动证据裁剪；`decision_prompt` 配置化；`RoutedHybridSignalDecisionAgent` 契约校验与失败回退 | `signal_decision_prompt_profiles.json`、`llm_signal_decision.schema.json` |
| workflow 主链路 | 主链路固定 `signal_decision -> execution_decider`；不再加载 legacy planner/gate；阶段输出固定为 `workflow_bridge+decision_trace` | `trade_event_workflow.py`、`test_pipeline_stage_output_guard.py` |
| execution 接口边界 | `risk_hints` 透传 `decision_mode/llm_parse_status/prompt_config_*`；`decision_confidence_source=agent_signal_decision`；`ExecutionPlan.sizing/allowance` 仅语义建议 | `decision_plan_adapter.py`、`runner_output_contract.md` |
| trace 与可观测性 | `DecisionTrace.routing` 完整记录路由/LLM 判定信息；`llm_contract_error_code` 枚举与 `llm_contract_errors<=8` 收敛 | `decision_trace.schema.json`、`test_decision_trace_semantic_boundary_guard.py` |
| 兼容层下线与守卫 | 兼容开关已删除；legacy 域模块降级为 deprecated；workflow 防回流 import 与文档边界守卫已就位 | `test_workflow_minimal_boundary_guard.py`、`test_refactor_plan_status_guard.py` |

3. 已完成状态清单（替代 Phase C/Phase D）
- 兼容层已下线：不再提供 legacy/minimal 双态切换，也不保留兼容壳 workflow。
- `DecisionTrace.routing.pipeline_mode` 固定为 `minimal`，用于观测链路完整性。
- `DecisionTrace` 已移除 `intent/rule_plan/strategy_gate_result/risk_gate` 历史语义快照字段，仅保留主链路可观测字段。
- `intent_resolver/rule_planner/strategy_gate/risk_gate/execution_planner` 历史域模块已物理删除，并由 `test_workflow_minimal_boundary_guard.py` 防止 workflow 回流 import。
- `horizon_policy_gate` 历史域模块已物理删除，不再作为 workflow 参数与运行时配置接入点。
- `ExecutionPlan.sizing/allowance` 在 agent->execution 链路中定义为语义建议字段，execution 可覆盖或忽略，最终以 execution 规则为准。
- 历史域模块相关单测已移除，保留“工作流防回流 + 文件不存在”守卫。
- execution 成为唯一最终动作裁决路径。

## 9. 验收标准

1. agent 输出只包含 `SignalDecision` 语义字段，无风控执行字段。
2. 任意输入下，最终动作仅由 `execution_service` 给出。
3. `news/social/onchain` 与结构事件统一经 `event_center_new` 输入 agent。
4. 路由后不同类型信号均可稳定产出 `accept/reject/uncertain`。
5. `DecisionTrace` 可复盘并可用于事后正确性验证。
