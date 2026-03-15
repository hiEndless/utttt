# UTaker 跨模块术语白名单

更新时间：2026-03-15

目标：统一跨服务字段术语，避免“字段名相同但语义漂移”或“历史术语误导实现”。

## 1. 决策方向（Direction）

- canonical：`long | short | neutral`
- 适用字段：
  - `agent.signal_direction`
  - `execution.direction_intent`
- 约束：
  - 非规范值 `none` 不作为对外契约值。
  - 观测/守卫中若出现 `none`，仅表示历史残留检测，不代表当前允许值。

## 2. 信号裁决（Signal Verdict）

- canonical：`accept | reject | uncertain`
- 适用字段：
  - `agent.signal_verdict`
  - `execution.risk_hints.signal_verdict`

## 3. 决策模式（Decision Mode）

- canonical：`llm | rule_fallback | rule`
- 适用字段：
  - `agent.decision_mode`
  - `execution.risk_hints.decision_mode`
- 说明：
  - `rule_fallback` 仅表示 LLM 载荷不可用时的回退路径，不代表旧链路回归。

## 4. LLM 解析状态（LLM Parse Status）

- canonical：`llm_ok | llm_invalid_payload | llm_status_not_ok | llm_not_provided | rule_only`
- 适用字段：
  - `agent.llm_parse_status`
  - `execution.risk_hints.llm_parse_status`

## 5. provider_state（alternative_sources）

- 不可用集合：`noop | empty | unavailable | none`
- 说明：
  - 该 `none` 属于 provider_state 语义，不等同于方向字段的历史 `none`。

## 6. 历史术语约束

- 以下术语仅允许出现在“迁移背景/历史说明”，不得用于当前主链路契约定义：
  - `legacy pipeline`
  - `intent/rule/strategy/risk/horizon/execution_planner` 历史域术语
  - 方向枚举中的 `none`
