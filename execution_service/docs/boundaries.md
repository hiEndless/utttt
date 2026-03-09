# execution_service 边界

## 输入边界

允许输入：

1. `agent_server_new` 的决策意图（方向、置信度、解释提示）
2. 仓位与账户状态（通过 `PositionStateProvider/AccountStateProvider`）
3. 风控策略配置

不允许输入：

1. 原始行情数据
2. 特征层原始结构
3. 事件中心原始事件流

## 输出边界

只输出执行层结果：

1. 最终动作
2. 拒绝原因
3. 应用规则
4. 执行回执（可选）

## 责任边界

1. 最终风险裁决权在 execution_service
2. agent 仅提供意图，不直接决定最终仓位动作
