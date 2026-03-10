# 语义防漂移护栏（P0/P1）

更新时间：2026-03-11

目标：防止“字段不报错但语义已错位”。

## P0（本轮）

1. 统一回放摘要契约类型
- `event_center_new/docs/replay_summary.schema.json` 的 `diffs` 与实现保持一致（`array[string]`）。

2. 收紧 selected_event 资产匹配
- `market_state_engine/adapters/selected_events_redis.py` 只接受：
  - `asset = "{exchange}:{symbol}"`（大小写不敏感，精确匹配）
  - `asset = "{symbol}"`（精确匹配）
- 禁止子串匹配，避免 `ETH` 命中 `ETHUSDT` 的误判。

3. 增加 MSL 合同门禁（agent 入口）
- `agent_server_new/adapters/market_state_http.py` 增加轻量校验：
  - `msl_meta.schema_version` 必须是已支持版本（当前 `1/2`）
  - `msl` 必须包含核心字段（`version/timestamp/symbol/...`）
  - 校验失败不抛错，追加 `anomaly_flags`，便于观测和回放告警。

## P1（下一步建议）

1. 给 MSL 增加独立 JSON Schema
- 现在 MSL 主要靠 dataclass + 白名单测试，建议补全 `market_state_engine/docs/msl.schema.json`。

2. 统一时间字段命名规范
- 事件/流转层统一 `ts_ms`；
- 资源快照元信息统一 `generated_at_ms/updated_at_ms`；
- 语义对象内部保留 `timestamp(ISO8601)` 时，必须同时提供 `ts_ms` 派生字段或转换规则。

3. 统一 confidence 语义命名
- `evidence_confidence`（证据置信度）
- `classification_confidence`（分类置信度）
- `decision_confidence`（决策置信度）
- 避免不同阶段都叫 `confidence` 且语义不同。

4. 收敛开放对象边界
- 逐步将 `additionalProperties: true` 改为白名单对象（尤其是 execution 输入输出契约）。

5. risk flags 结构标准化
- 同名字段禁止异构（例如 `risk_flags` 同时出现 `dict/list`）。
- 约定：`risk_flags` 统一为 `array[string]`，若需数值明细放 `risk_metrics`。

