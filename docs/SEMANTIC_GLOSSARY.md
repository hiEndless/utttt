# UTaker 语义词典（防漂移）

更新时间：2026-03-11

目标：防止“字段不报错但语义悄悄错位”。

## 1. 核心原则

- 同一个语义对象只允许一个 canonical source。
- 同一个字段名在全链路必须是同一语义。
- 若语义变化，必须先升版 schema，再变更代码。

## 2. 关键字段定义（冻结）

### 2.1 confidence

- `decision_confidence`
  - 语义：agent 对“交易方向意图”的决策置信度。
  - 范围：`execution_service` 的 `DecisionIntent` 主字段。
  - 约束：`level=low|medium|high`，`score in [0,1]`。
- `confidence`（deprecated）
  - 语义：`decision_confidence` 的兼容别名。
  - 约束：若同时出现，必须与 `decision_confidence` 完全一致。
- `evidence_confidence`
  - 语义：事件证据强度（事件层）。
- `classification_confidence`
  - 语义：事件分类模型置信度（事件层）。

禁止：把 `decision_confidence` 解释成“结构确认度”或“事件证据置信度”。

### 2.2 risk_bias

- 当前状态：未冻结为跨服务标准字段。
- 规则：新链路禁止把 `risk_bias` 作为自由语义字段直接传播。
- 建议：在 schema 正式冻结前，仅允许出现在模块内私有对象，不进入跨服务契约。

### 2.3 market_state

- `raw_market_structure`
  - 语义：上游结构化原始输入（未融合结论）。
  - canonical source：`feature_service`。
- `msl`（Market Structure Language）
  - 语义：状态层融合后的结构结论（供 agent 决策）。
  - canonical source：`market_state_engine`。

禁止：把 `raw_market_structure` 当作 `msl` 使用，或反向替代。

## 3. 时间字段定义（冻结）

- `ts_ms`：毫秒时间戳主字段（int）。
- `ts`：兼容别名（若存在，必须与 `ts_ms` 同值）。
- `timestamp`：ISO8601 字符串，仅用于 MSL/人读上下文，不用于事件排序主键。

## 4. 风险标记字段定义（冻结）

- `risk_flags`：风险特征标签集合（可多值），用于风险暴露描述。
- `risk_state`：风险状态机离散状态（如 `normal|warn|reduce_only|frozen`），用于动作约束。

禁止：将 `risk_flags` 误用为状态机状态，或将 `risk_state` 当作可叠加标签集合。

## 5. 变更流程（必须）

1. 修改 schema（含 required/enum/字段语义注释）。
2. 升级版本号（如 schema mapping version）。
3. 更新本词典与服务 API 文档。
4. 通过契约守卫后方可合并。

## 6. 字段弃用生命周期模板

目标：让字段去兼容过程可审计、可回滚、可自动化守卫。

### 6.1 阶段定义

1. `active`
- 字段为主字段，可作为唯一输入来源。
- 所有新功能只能基于 `active` 字段扩展。

2. `deprecated`
- 字段保留兼容读取，但不再作为语义主字段。
- 新 producer 禁止仅写 deprecated 字段。
- 若存在主字段与 deprecated 字段双写，必须一致。

3. `removed`
- 字段从 schema 中移除，并在 domain 解析层拒绝输入。
- 文档与示例中禁止再出现该字段。

### 6.2 进入条件（建议）

从 `active -> deprecated`：
- 已有替代主字段并完成 schema 显式声明。
- 契约守卫覆盖“双字段一致性”或“兼容回退”路径。

从 `deprecated -> removed`：
- 连续观测窗口（建议 30 天）`deprecated_only_requests = 0`。
- 连续观测窗口 `alias_mismatch_rejections = 0`。
- 所有下游联调脚本与 SDK 已升级。

### 6.3 回滚规则

- 若升级后出现兼容故障，可临时回滚到上一稳定提交。
- 回滚期只允许短期恢复兼容，不允许长期跳过一致性校验。
- 回滚后必须在文档记录：触发时间、影响范围、恢复条件。

### 6.4 模板示例（Decision Confidence）

- `decision_confidence`: `active`
- `confidence`: `deprecated`
- 计划在 `execution-contract-v2` 评审通过后推进 `confidence -> removed`
