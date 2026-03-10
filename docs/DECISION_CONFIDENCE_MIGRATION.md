# Decision Confidence 迁移计划（v1 -> v1.5）

更新时间：2026-03-11

目标：把执行链路中的决策置信度语义统一到 `decision_confidence`，并避免 `confidence` 在不同模块语义漂移。

## 1. 当前约束（已落地）

1. agent -> execution payload 同时携带：
- `decision_confidence`
- `confidence`（兼容）

2. execution 输入解析规则：
- 优先读取 `decision_confidence`。
- 若同时提供 `confidence`，两者必须一致，否则拒绝（`400`）。

3. execution 输出（内部对象转字典）同时回写：
- `decision_confidence`
- `confidence`（兼容）

## 2. 分阶段迁移（含日期）

1. Phase A（2026-03-11 ~ 2026-04-30）
- 双写双读阶段。
- 目标：所有上游生产方都能发出 `decision_confidence`。
- 守卫：不允许双字段数值不一致。

2. Phase B（2026-05-01 ~ 2026-06-30）
- 上游规范化阶段。
- 要求：新增/改造 producer 必须以 `decision_confidence` 作为主字段。
- `confidence` 仅作为兼容镜像，不再单独维护。

3. Phase C（从 2026-07-01 起）
- 进入破坏性升级准备窗口（Execution Contract v2 候选）。
- 计划：在 v2 中移除 `confidence`，仅保留 `decision_confidence`。
- 前置条件：至少连续 30 天无 `confidence`-only 请求。

## 3. 风险与回滚

1. 风险：旧客户端仅发送 `confidence`
- 处理：Phase A/B 仍兼容，不会中断。

2. 风险：双字段不一致导致请求失败
- 处理：这是显式保护策略，优先保证语义一致，不做静默覆盖。

3. 回滚策略
- 若出现大规模兼容问题，可临时放宽为“记录告警 + 采用 `decision_confidence`”，但需在一周内恢复一致性校验。

4. v2 触发门槛
- 建议门槛：连续 30 天 `confidence_only_requests=0` 且 `confidence_alias_mismatch_rejections=0`。
- 通过门槛后，才进入 `execution-contract-v2` 的去兼容评审与发布窗口。

## 4. 对齐清单

1. 文档
- `execution_service/docs/api.md`
- `docs/CONTRACTS_QUICK_REF.md`
- `execution_service/docs/migration.md`

2. 契约
- `execution_service/docs/decision_intent.schema.json`
- `execution_service/domain/contracts.py`

3. 测试
- `execution_service/text/test_decision_intent_contract.py`
- `execution_service/text/test_decision_intent_schema.py`

4. 观测接口
- `GET /internal/execution/debug/confidence-metrics`
- 可选持久化：`EXECUTION_CONFIDENCE_METRICS_MODE=redis`（默认 memory）
- 调试重置：`POST /internal/execution/debug/confidence-metrics/reset`（需 `EXECUTION_DEBUG_ALLOW_METRICS_RESET=true`）
