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

## 关键收敛决议（冻结）

1. `Position Context` 由 execution_service 侧读取与使用
2. agent 不再以 `Position Context` 作为裁决输入
3. execution_service 成为最终动作裁决权威（add/reduce/hold/exit/skip）
