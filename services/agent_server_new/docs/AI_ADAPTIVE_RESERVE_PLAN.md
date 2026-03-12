# agent_server_new AI 自适应策略预留升级建议（v1）

更新时间：2026-03-10

本文档目标：在不打断当前主线开发的前提下，为后续“AI 自适应策略”提供最小可行预留。

## 1. 结论

建议采用“主线继续 + 轻预留先行”：

1. 当前版本继续按既定新架构开发（不做大重构）。
2. 立即预留契约、反馈、开关、观测 4 类能力。
3. 执行层保持“AI 建议 + 脚本硬风控兜底”，不做 AI 直接替代。

## 2. 预留原则

1. 不改变现有职责边界：
- `agent_server_new` 负责决策与解释
- `execution_service` 负责最终风控与动作裁决

2. 所有新增能力默认关闭（Feature Flag）：
- 预留字段可为空
- 未开启时行为必须与当前一致

3. 保持向后兼容：
- 新增字段只增不改
- 不破坏既有 `DecisionIntent/ExecutionResult` 主契约

## 3. 建议预留点

## 3.1 契约预留（agent -> execution）

在现有 payload 中增加可选字段：

1. `execution_hint`（对象）
- 示例：`{"mode":"split_order","slices":3,"urgency":"low"}`

2. `adaptive_profile`（对象）
- 示例：`{"profile_id":"trend_follow_v1","size_multiplier":0.8,"open_threshold":0.65}`

3. `adaptive_profile_version`（字符串）
- 示例：`"ap-2026-03-10-001"`

4. `adaptive_explain`（对象，可选）
- 示例：`{"reason_codes":["regime_trend","volatility_normal"]}`

说明：以上字段仅作为建议输入，execution 仍按硬规则最终裁决。

## 3.2 反馈事件预留（feedback loop）

新增统一反馈结构（先定义文档，不要求立即全量落地）：

1. `decision_id`
2. `exchange`
3. `symbol`
4. `regime`（来自 market_state）
5. `agent_action/agent_direction`
6. `execution_action/reject_reason`
7. `pnl_horizon`（如 5m/30m/4h）
8. `mae/mfe/slippage`
9. `ts`

## 3.3 存储预留

1. 在线：Redis（短窗口、低延迟）
2. 离线：DB（审计与复盘）

当前决策：DB 归档暂不实现，按代办推进：
- `services/agent_server_new/docs/MEMORY_ARCHIVE_TODO.md`

## 3.4 开关与灰度预留

新增开关（建议命名）：

1. `AGENT_AI_ADAPTIVE_ENABLED=false`
2. `AGENT_AI_ADAPTIVE_MODE=observe|recommend|bounded_apply`

语义：

1. `observe`：仅记录，不参与决策
2. `recommend`：输出建议，不改变最终动作
3. `bounded_apply`：在 execution 硬边界内生效

## 3.5 观测预留

建议新增指标：

1. `adaptive_profile_hit_rate`
2. `adaptive_recommend_accept_rate`
3. `adaptive_delta_pnl`（与固定策略对照）
4. `adaptive_reject_rate_by_rule`
5. `adaptive_switch_frequency`

## 4. 分阶段实施建议

## Phase A（预留，1-2 天）

1. 文档冻结字段与开关
2. 在契约层增加可选字段（默认不使用）
3. 增加最小测试（开关关闭行为不变）

## Phase B（观测，3-5 天）

1. 打通 feedback 记录与指标面板
2. `recommend` 模式上线（不改最终执行）
3. 完成固定策略 vs 建议策略的离线回放对比

## Phase C（受控生效，1-2 周）

1. `bounded_apply` 小流量灰度
2. 只允许 AI 调整软参数（如 size multiplier），禁止越过硬风控
3. 增加 kill-switch 与自动回退

## 5. 现在不建议做的事

1. 不要让 AI 直接替代 execution 硬风控脚本。
2. 不要在没有回放验证前直接全量启用自适应策略。
3. 不要在单笔结果上做强烈参数切换（避免抖动与过拟合）。

## 6. 与现有架构的兼容性评估

当前架构已具备预留基础：

1. `market_state_engine -> agent_server_new -> execution_service` 分层明确
2. `agent_server_new` 已有 `DecisionTrace` 与 memory 观测能力
3. `execution_service` 已具备可配置 risk policy provider（可承接受控参数）

综合评估：当前做预留改造难度低（约 3/10），工期短（1-2 天）。

## 7. 验收标准（预留阶段）

1. 开关关闭时，行为与当前版本完全一致。
2. 新字段缺失不影响联调与执行。
3. 观测链路可区分：固定策略结果 vs 自适应建议结果。
4. 文档与测试同步更新，避免“有代码无约定”。
