# 语义防漂移护栏（v14）

更新时间：2026-03-11

目标：防止“字段不报错但语义已错位”。

## 已落地基线

1. 统一回放摘要契约类型
- `services/event_center_new/docs/replay_summary.schema.json` 的 `diffs` 与实现保持一致（`array[string]`）。

2. 收紧 selected_event 资产匹配
- `services/market_state_engine/src/adapters/selected_events_redis.py` 只接受：
  - `asset = "{exchange}:{symbol}"`（大小写不敏感，精确匹配）
  - `asset = "{symbol}"`（精确匹配）
- 禁止子串匹配，避免 `ETH` 命中 `ETHUSDT` 的误判。

3. 增加 MSL 合同门禁（agent 入口）
- `services/agent_server_new/adapters/market_state_http.py` 增加轻量校验：
  - `msl_meta.schema_version` 必须是已支持版本（当前 `1/2`）
  - `msl` 必须包含核心字段（`version/timestamp/symbol/...`）
  - 校验失败不抛错，追加 `anomaly_flags`，便于观测和回放告警。

4. 时间字段兼容别名（非破坏）
- `event_center_new` runner health 同时写入 `updated_ms` 与 `updated_at_ms`。
- `market_state_engine` `/healthz`、`/version` 与状态查询响应同时返回 `ts` 与 `ts_ms`。
- `execution_service` `/healthz` 与 `/version` 同时返回 `ts` 与 `ts_ms`。
- `agent_server_new.strategy_gate_v2` 时间读取优先 `event_ts_ms`，兼容 `ts_ms/timestamp_ms/ts/generated_at_ms/timestamp(ISO8601)`。

5. `risk_flags` 语义标准化（非破坏）
- `market_state_engine` 聚合层统一输出 `risk_flags: array[string]`。
- 原 map 细节（布尔位/数值位）保留到 `risk_metrics`，避免信息丢失。
- `agent_server_new` 上下文构建对 `oi_risk_flags` 做 list/map 双输入归一化，避免字段类型漂移影响决策提示。

6. `decision_confidence` 语义冻结（execution v14）
- `DecisionIntent` 主字段为 `decision_confidence`（必填）。
- `confidence` 为 deprecated 兼容字段，仅允许作为镜像字段存在。
- 双字段同时出现时必须一致（不一致返回 `400`）。
- `decision_confidence.schema.json` 已抽取为共享结构，禁止在业务 schema 内重复定义。

7. execution 契约去重与收敛
- `execution_io_payload.schema.json` 复用 `order_result/reconcile_result` 公共结构。
- `execution_enums.schema.json` 复用 `direction_intent/execution_action/io_mode/io_status/request_side/request_type`。
- `execution_schema_mapping_version` 当前为 `execution-schema-mapping-v15`。
- `feature_response_schema_version` 当前为 `1.0`。
- `market_state_contract_version` 当前为 `market-state-contract-v1`。
- `market_state_msl_schema_version` 当前为 `2`。

## 后续建议

1. 强化 v2 去兼容门槛
- 连续 30 天 `confidence_only_requests=0` 且 `confidence_alias_mismatch_rejections=0` 后，再评审移除 `confidence` 字段。
- 进入 v2 前，要求所有上游 producer 契约测试通过 `decision_confidence` 必填守卫。

2. 统一时间字段命名规范
- 事件语义层统一 `event_ts_ms`（发生）与 `processed_ts_ms`（处理）；
- `ts_ms` 仅作为兼容别名保留在过渡窗口；
- 资源快照元信息统一 `generated_at_ms/updated_at_ms`；
- 语义对象内部保留 `timestamp(ISO8601)` 时，必须同时提供毫秒级字段（`event_ts_ms/processed_ts_ms` 或显式映射规则）。

3. 扩展 confidence 语义字典到全链路
- `evidence_confidence`（证据置信度）
- `classification_confidence`（分类置信度）
- `decision_confidence`（决策置信度）
- 禁止新增裸字段 `confidence`（除兼容镜像位）。

4. 收敛开放对象边界
- 逐步将 `additionalProperties: true` 改为白名单对象（尤其是 execution 输入输出契约）。

5. risk flags 结构标准化
- 同名字段禁止异构（例如 `risk_flags` 同时出现 `dict/list`）。
- 约定：`risk_flags` 统一为 `array[string]`，若需数值明细放 `risk_metrics`。
