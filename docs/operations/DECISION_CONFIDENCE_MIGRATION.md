# Decision Confidence 基线说明（v14）

更新时间：2026-03-11

目标：把执行链路中的决策置信度语义统一到 `decision_confidence`，并避免 `confidence` 在不同模块语义漂移。

## 1. 当前约束（已落地）

1. agent -> execution payload
- `decision_confidence`：主字段（必填）
- `confidence`：deprecated 兼容字段（可选）

2. execution 输入解析规则
- 以 `decision_confidence` 为准。
- 若同时提供 `confidence`，两者必须一致，否则拒绝（`400`）。

3. execution 输出（内部对象转字典）
- 同时回写 `decision_confidence` 与 `confidence`（兼容镜像）。

## 2. 当前版本状态

1. 契约版本
- `execution_schema_mapping_version = execution-schema-mapping-v17`
- `DecisionIntent` 已要求 `decision_confidence` 必填。

2. 契约复用
- `decision_confidence.schema.json`：统一置信度结构。
- `decision_intent.schema.json` 中 `confidence/decision_confidence` 已统一 `$ref` 到该 schema。

3. 兼容策略
- `confidence` 仍保留（deprecated），用于平滑兼容旧生产方。
- 兼容期内不允许双字段不一致（硬拒绝）。

## 3. 风险与回滚

1. 风险：旧客户端仅发送 `confidence`
- 处理：当前会被拒绝（`decision_confidence` 必填）；需通过适配器升级调用方。

2. 风险：双字段不一致导致请求失败
- 处理：这是显式保护策略，优先保证语义一致，不做静默覆盖。

3. 回滚策略
- 若出现大规模兼容问题，可临时回滚到上一稳定提交，恢复更宽兼容窗口。
- 回滚窗口仅用于应急，需在一周内恢复一致性校验。

4. v2 触发门槛（移除 `confidence`）
- 建议门槛：连续 30 天 `confidence_only_requests=0` 且 `confidence_alias_mismatch_rejections=0`。
- 通过门槛后，才进入 `execution-contract-v2` 的去兼容评审与发布窗口。

## 4. 对齐清单

1. 文档
- `services/execution_service/docs/api.md`
- `docs/CONTRACTS_QUICK_REF.md`
- `services/execution_service/docs/migration.md`

2. 契约
- `services/execution_service/docs/decision_intent.schema.json`
- `services/execution_service/domain/contracts.py`

3. 测试
- `verification/validators/execution_service/test_decision_intent_contract.py`
- `verification/validators/execution_service/test_decision_intent_schema.py`

4. 观测接口
- `GET /internal/execution/debug/confidence-metrics`
- 可选持久化：`EXECUTION_CONFIDENCE_METRICS_MODE=redis`（默认 memory）
- 调试重置：`POST /internal/execution/debug/confidence-metrics/reset`（需 `EXECUTION_DEBUG_ALLOW_METRICS_RESET=true`）
