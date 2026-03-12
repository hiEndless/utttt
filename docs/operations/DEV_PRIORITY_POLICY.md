# Dev Priority Policy

更新时间：2026-03-12

## 1. 目标

在重构后半程，开发优先级统一为：

1. 先做业务能力落地（可产出真实业务价值）
2. 再做最小必要验证（防止字段语义漂移）
3. 最后补守卫与自动化（固化已稳定能力）

## 2. 业务优先顺序

1. `services/feature_service`
- 优先完善可直接影响下游决策质量的特征产出（结构、风险、跨周期一致性）。

2. `services/market_state_engine`
- 优先完善 MSL 生成逻辑与状态解释层，减少“字段存在但语义偏移”。

3. `services/agent_server_new`
- 优先完善决策上下文使用与信号解释一致性（避免同字段多语义）。

4. `services/execution_service`
- 优先完善执行与回执语义闭环（方向、原因、风控拒绝路径一致）。

5. `services/event_center_new`
- 优先保证 selected_event 语义稳定与下游消费一致，不追求过度治理脚本。

## 3. 字段漂移最小检查清单（每次业务改动后）

1. `schema_version` 是否与文档/manifest 一致。
2. `confidence` 是否仍只表达既定语义（不得混用模型置信度/结构确认度）。
3. `market_state` 是否区分原始分析与融合结论（不得混用）。
4. `risk_flags` / `risk_state` 是否类型与含义稳定。
5. 时间字段是否遵守口径：
- 事件用 `event_ts_ms` / `processed_ts_ms`
- 兼容字段 `ts_ms` 不得替代语义字段
6. 同一语义对象是否仍只有一个 canonical source。

## 4. 开发节奏约束

1. 单次迭代优先提交业务改动，不要求先补齐全部守卫。
2. 守卫只做“最小必要补充”，避免守卫先于业务占用主要精力。
3. 对高风险字段改动，至少保留一条可复现实例（fixture/replay case）。

## 5. 当前阶段建议

1. 下一阶段主线放在 `feature_service + market_state_engine`。
2. 先收敛字段语义，再考虑新增复杂验证脚本。
3. 每个业务迭代结束时，只做最小字段漂移核对与一轮关键链路回归。
