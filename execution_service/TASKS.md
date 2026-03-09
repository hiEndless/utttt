# execution_service 任务列表

- [x] Task 1: 冻结 `DecisionIntent` 输入契约（字段 + 文档示例 + 端口类型）。
- [x] Task 2: 冻结 `ExecutionResult` 输出契约（动作枚举 + 拒绝码 + 文档示例）。
- [x] Task 3: 定义 `position/account` provider ports，并提供最小 stub 实现。
- [x] Task 4: 实现确定性执行裁决器（仓位上限/冷却期/回撤阈值/方向冲突）。
- [x] Task 5: 接入最小 API（`POST /internal/execution/decide` + `GET /internal/execution/healthz`）。
- [x] Task 6: 打通 `agent_server_new -> execution_service` 最小联调用例。
- [x] Task 7: 增加 `state -> agent -> execution` 链路守卫脚本并接入 CI 入口。
- [x] Task 8: 新增 Redis 状态 providers（position/account/risk_policy），并支持 `stub/redis` 模式切换。
- [x] Task 9: 扩展 agent->execution 守卫脚本，纳入 Redis/providers 模式测试。
- [x] Task 10: 新增 Redis 集成测试（binance/ETHUSDT），验证 execution_service 真实 Redis 裁决链路。
- [x] Task 11: 冻结 Redis key 契约文档（position/account/risk_policy）并同步入口文档。
- [x] Task 12: 新增 execution debug 状态接口（/debug/state/{exchange}/{symbol}）并补 API 测试。
- [x] Task 13: debug 状态接口支持 `redact` 脱敏参数，并同步 API/README 文档。
- [x] Task 14: 新增 `/internal/execution/version` 版本接口并补 API 测试。
- [x] Task 15: 扩展 agent->execution 守卫脚本，纳入 execution API（含 /version）测试。
- [x] Task 16: 新增 execution_service cURL 示例文档（stub/redis 双模式）并同步入口文档。
- [x] Task 17: 新增 execution_service HTTPie 示例文档并同步入口文档。
- [x] Task 18: 新增项目级契约索引文档并补 runner 输出 schema 独立守卫。
