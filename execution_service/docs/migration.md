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

## 关键收敛决议（冻结）

1. `Position Context` 由 execution_service 侧读取与使用
2. agent 不再以 `Position Context` 作为裁决输入
3. execution_service 成为最终动作裁决权威（add/reduce/hold/exit/skip）
