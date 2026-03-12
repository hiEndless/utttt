# agent_server_new 重构方案（V2）

更新时间：2026-03-10

## 1. 目标

将 `agent_server_new` 收敛为“方向判断与决策编排层”，把仓位与风控最终裁决下沉到 `execution_service`（确定性脚本服务）。

目标能力边界：

1. 保留：
- 信号方向判断与解释
- 多周期冲突建议消费（`cross_horizon.suggested_policy`）
- 轻量策略门控（HorizonPolicyGate / StrategyGate）
- 决策可观测（DecisionTrace）

2. 下沉：
- 仓位上限与加仓约束
- PnL 驱动风控
- 账户级风险约束
- 最终执行动作裁决

## 2. 目标架构

```text
feature_service
  -> market_state_engine
    -> agent_server_new
      -> execution_service
```

触发方式（双轨）：

1. 主链路：事件中心触发（实时）  
`event_center_new(signal_event)` -> `agent_server_new`

2. 辅链路：定时巡检（补漏）  
`state_refresh_event` -> `agent_server_new`

## 3. 输入上下文（冻结）

当前统一输入结构：

`MSL -> Key Evidence -> Active Events -> Signal Event`

说明：

1. `MSL`：主语境（趋势、阶段、流动性、风险）
2. `Key Evidence`：按事件类型动态裁剪证据
3. `Active Events`：背景事件
4. `Signal Event`：触发事件本体
5. `Position Context`：下沉到 `execution_service`，不再进入 agent 裁决输入

补充字段（已落地）：
- `msl_meta`
- `msl_bundle`
- `cross_horizon`（含 `suggested_policy`）

## 4. agent 职责收敛策略

### 4.1 当前到目标的迁移

阶段 A（当前）：
- agent 内仍包含 `IntentResolver/RulePlanner/RiskGate/ExecutionPlanner`

阶段 B（目标）：
- agent 只输出方向与决策解释
- execution_service 接收方向意图并结合 `Position Context` 做最终执行裁决

### 4.2 推荐中间态

1. `SignalEvaluator` 保留（语义判断）
2. `HorizonPolicyGate` 保留（冲突快速收敛）
3. `IntentResolver` 保留但仅生成轻量意图
4. `RulePlanner/ExecutionPlanner` 逐步瘦身为“建议”，不做最终风控裁决

## 5. HorizonPolicyGate（已完成）

状态：

1. 已独立模块化：`agent_server_new/domain/horizon_policy_gate.py`
2. 已支持配置驱动：
- `block_on_increase_policies`
3. 已支持环境变量：
- `AGENT_HORIZON_POLICY_BLOCK_ON_INCREASE`（CSV）
- `AGENT_HORIZON_POLICY_CONFIG_JSON`（JSON）

## 6. 运行与装配（已完成）

1. 默认工厂：
- `agent_server_new.app.create_trade_event_workflow_from_env`

2. CLI：
- `python -m services.agent_server_new.main --dry-run`

3. one-shot pipeline smoke：
- `python -m services.agent_server_new.pipeline_smoke --dry-run`
- 单进程串联 `market_state_engine -> agent_server_new`

## 7. 与 execution_service 的契约方向

建议 agent 输出给 execution 的对象：

1. `decision_id`
2. `symbol/exchange`
3. `direction_intent`（long/short/none）
4. `confidence`
5. `explanation_tags`
6. `cross_horizon_policy`
7. `risk_hints`（非最终约束）

execution_service 最终输出：

1. `execution_action`（add/reduce/hold/exit/skip）
2. `reject_reason`（如 `position_limit_reached`）
3. `applied_risk_rules`
4. `order_result`（如有）

## 8. 分阶段实施计划

1. Phase 1（已完成）：
- 输入契约收敛（MSL + msl_meta + msl_bundle + cross_horizon）
- HorizonPolicyGate 落地与配置化

2. Phase 2（进行中）：
- `agent -> execution_service` 输出契约冻结
- 把仓位/风控硬规则下沉到 execution
 - 可选 `execution_decider` 已接入 workflow（`AGENT_EXECUTION_ENABLED=true` 时生效）
- DecisionTrace schema 冻结：新增 `docs/decision_trace.schema.json`，锁定 `llm_observation.status/provider/model/raw_content_hash`

3. Phase 3（待开始）：
- agent 内 `RulePlanner/ExecutionPlanner` 改为建议层
- execution_service 成为唯一执行裁决权威

## 9. 验收标准

1. agent 不依赖旧 MSL 字段（已覆盖守卫）
2. `cross_horizon.suggested_policy` 进入决策链路（已完成）
3. one-shot pipeline 可跑通（已完成）
4. execution_service 对仓位与风险有最终裁决权（待完成）
