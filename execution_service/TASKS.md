# execution_service 任务列表

- [x] Task 1: 冻结 `DecisionIntent` 输入契约（字段 + 文档示例 + 端口类型）。
- [x] Task 2: 冻结 `ExecutionResult` 输出契约（动作枚举 + 拒绝码 + 文档示例）。
- [x] Task 3: 定义 `position/account` provider ports，并提供最小 stub 实现。
- [x] Task 4: 实现确定性执行裁决器（仓位上限/冷却期/回撤阈值/方向冲突）。
- [x] Task 5: 接入最小 API（`POST /internal/execution/decide` + `GET /internal/execution/healthz`）。
- [ ] Task 6: 打通 `agent_server_new -> execution_service` 最小联调用例。
- [ ] Task 7: 增加 `state -> agent -> execution` 链路守卫脚本并接入 CI 入口。
