# UTaker 新架构迁移执行清单（Playbook）

更新时间：2026-03-10

## 1. 目标冻结

目标链路：

```text
event_center_new(signal_event + active_events)
  + market_state_engine(MSL + Key Evidence)
    -> agent_server_new(方向裁决与解释)
      -> execution_service(仓位/账户/PnL 风控 + 最终动作裁决)
```

冻结原则：
- agent 输入固定为：`MSL -> Key Evidence -> Active Events -> Signal Event`
- `Position Context` 不进入 agent 裁决输入
- execution_service 是最终动作裁决权威（`add/reduce/hold/exit/skip`）

## 2. 分阶段任务（按顺序执行）

### Phase A: 契约冻结（文档与类型先行）

1. 冻结 `agent -> execution` 输入契约
- 修改模块：`services/execution_service/ports/decision_intent.py`、`services/execution_service/docs/api.md`
- 最小字段：`decision_id/exchange/symbol/direction_intent/confidence/cross_horizon_policy/risk_hints`
- 验收：契约文档与类型定义一致

2. 冻结 execution 输出契约
- 修改模块：`services/execution_service/ports/execution_result.py`、`services/execution_service/docs/api.md`
- 最小字段：`execution_action/reject_reason/applied_risk_rules/order_result`
- 验收：拒绝码字典与示例响应一致

### Phase B: execution 最小闭环（确定性裁决）

3. 接入 position/account provider
- 修改模块：`services/execution_service/ports/position_provider.py`、`services/execution_service/ports/account_provider.py`
- 验收：可以读取仓位、账户风险暴露、PnL 快照

4. 落地确定性风控裁决器
- 修改模块：`services/execution_service/domain/risk_rules.py`、`services/execution_service/domain/decision_engine.py`
- 规则优先级：仓位上限 > 冷却期 > 回撤阈值 > 方向冲突
- 验收：同输入必然同输出（纯函数可测）

5. 暴露最小 HTTP API
- 修改模块：`services/execution_service/app/service.py`、`services/execution_service/routes.py`
- 接口：`POST /internal/execution/decide`、`GET /internal/execution/healthz`
- 验收：可接收 agent 输出并返回最终动作

### Phase C: agent workflow 收敛（去执行化）

6. 缩减 agent workflow 到“方向裁决核心链”
- 修改模块：`services/agent_server_new/app/workflows/trade_event_workflow.py`
- 目标链路：`SignalEvaluator -> HorizonPolicyGate -> DirectionDecision`
- 验收：不再在 agent 内做仓位/PnL 风控硬裁决

7. agent 输出改为 execution 输入对象
- 修改模块：`services/agent_server_new/domain/contracts.py`、`services/agent_server_new/ports/execution_plan_sink.py`
- 验收：输出字段可直接投递到 `execution_service /decide`

### Phase D: 联调与守卫

8. 增加端到端守卫
- 修改模块：`tools/local/check_state_to_agent_contract_guard.sh`（补 execution 链路）
- 新增：`tools/local/check_agent_to_execution_guard.sh`
- 验收：CI 可一键校验 `state -> agent -> execution` 主链路

## 3. 里程碑验收标准

M1（契约冻结）：
- 文档、类型、示例三者一致

M2（execution 可裁决）：
- 已有拒绝码与可解释的 `applied_risk_rules`

M3（agent 收敛完成）：
- agent 不读取 `position_context`
- agent 不做最终执行动作裁决

M4（全链路联调）：
- 主链路在脚本守卫中通过

## 4. 风险与回退

- 风险 1：agent 与 execution 契约漂移  
  处理：先冻结 ports，再落代码，最后补守卫。

- 风险 2：收敛过程中策略行为突变  
  处理：双写一段时间（旧 ExecutionPlan + 新 DecisionIntent），对比日志后切换。

- 风险 3：event_center_new 重构未完成影响主链路验证  
  处理：先用固定 `signal_event` fixture 跑通 `state -> agent -> execution`。
