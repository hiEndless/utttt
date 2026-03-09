# agent_server_new Symbol 记忆层升级计划（v1）

更新时间：2026-03-10

## 1. 背景与目标

当前 `agent_server_new` 以“单次事件 + 当前状态快照”驱动决策，缺少同一 `symbol` 的长期行情连续性记忆。

本计划目标：

1. 增加 `symbol` 级市场记忆（不包含仓位信息）。
2. 在不改主链路的前提下，给决策提供长期背景。
3. 保持 `execution_service` 的仓位/账户/风控边界不变。

冻结边界：

1. `memory` 只服务决策背景，不承载执行风控。
2. `memory` 不写入具体持仓、订单、账户余额等执行侧数据。
3. `memory` 以结构化存储为主，Markdown 为可读投影。

## 2. 架构影响评估

影响范围：`agent_server_new` 内部增量改造，主链路不变。

```text
event_center_new + market_state_engine
  -> agent_server_new
     (ContextBuilder 注入 symbol_memory)
  -> execution_service
```

变更类型：

1. 新增 ports（读/写记忆端口）
2. 新增 adapters（Redis/DB 或 in-memory）
3. ContextBuilder 增加 `memory_summary/recent_memory` 注入
4. Workflow 在决策后写入 memory raw 记录

不变项：

1. `feature_service`、`market_state_engine` 对外契约
2. `agent -> execution_service` 的 `DecisionIntent` 主契约
3. `execution_service` 的最终裁决职责

## 3. 存储方案建议

建议采用“双层记忆”：

1. Layer A: `memory_raw`（结构化流水）
- 每次决策写入一条。
- 用于审计、回放、重建摘要。

2. Layer B: `memory_summary`（可消费摘要）
- 每个 `exchange:symbol` 滚动维护。
- 决策时直接读取，控制 token 与噪声。

Markdown 策略：

1. 不作为主存储。
2. 作为定时导出（日报/周报/阶段复盘）。

## 4. 迭代阶段

## Phase 0（最小可用，2-4 天）

目标：接入最小记忆闭环，不影响现有线上行为。

1. 新增 `MemoryProvider`/`MemoryRecorder` ports。
2. 新增 `InMemorySymbolMemoryAdapter`（仅本进程，便于联调）。
3. `ContextBuilder.build()` 注入：
- `key_market_features.features += memory_summary`
- `key_market_features.features += recent_memory`
4. `TradeEventWorkflow.run_with_result()` 在输出后调用 `record_symbol_memory(...)`。
5. 增加开关：
- `AGENT_SYMBOL_MEMORY_ENABLED=false`（默认关闭）

验收：

1. 开关关闭时，行为与当前完全一致。
2. 开关开启时，决策上下文可见记忆特征。
3. 单测覆盖注入与回写链路。

## Phase 1（可持久化，1-2 周）

1. 新增 `RedisSymbolMemoryAdapter`（在线）。
2. 增加 TTL、Top-K、去重规则。
3. 增加 `summary` 后台整理任务（规则化，不引入独立 agent）。
4. 指标观测：记忆命中率、摘要长度、信号反转率变化。

当前进度（2026-03-10）：

1. `RedisSymbolMemoryAdapter` 已落地（含 TTL + Top-K + symbol index）。
2. 上下文注入侧已落地 TTL/去重/Top-K 过滤。
3. 已新增后台整理骨架：
- job：`agent_server_new/app/jobs/symbol_memory_summary_job.py`
- runner：`python -m agent_server_new.memory_summary_runner`

## Phase 2（生产增强，2-4 周）

1. 增加 DB 归档（审计与复盘）。
2. 增加 replay 对照（有/无 memory 策略差分）。
3. 定时导出 Markdown 复盘文档（仅投影层）。

当前决策（2026-03-10）：

1. DB 归档暂不实现代码。
2. 作为代办保留到文档：`agent_server_new/docs/MEMORY_ARCHIVE_TODO.md`
3. 后续按代办文档中的建议表结构创建归档工程与迁移脚本。

## 5. 第一优先改造建议（可立即开工）

第一步建议：先做 **Phase 0 的端口与注入骨架**，不引入外部依赖。

建议修改点：

1. 新增端口文件
- `agent_server_new/ports/memory/symbol_memory_provider.py`
- `agent_server_new/ports/memory/symbol_memory_recorder.py`
- 定义：
  - `get_symbol_memory(exchange, symbol, limit) -> Dict[str, Any]`
  - `record_symbol_memory(exchange, symbol, payload) -> None`

2. 新增最小 adapter
- `agent_server_new/adapters/symbol_memory_inmemory.py`
- 行为：
  - 内存字典按 `exchange:symbol` 维护 `raw` 列表与 `summary`。
  - 支持 `limit` 截断与去空字段。

3. 改造 `ContextBuilder`
- 文件：`agent_server_new/app/context_builder.py`
- 增加可选依赖 `symbol_memory_provider`。
- 在 `_signal_context_builder` 结果中追加：
  - `{"name":"memory_summary","value":...}`
  - `{"name":"recent_memory","value":[...]}`

4. 改造 `TradeEventWorkflow`
- 文件：`agent_server_new/app/workflows/trade_event_workflow.py`
- 增加可选依赖 `symbol_memory_recorder`。
- 在流程尾部写入 `memory_raw`（event/msl摘要/signal/intent/plan/execution_result）。

5. 改造 bootstrap
- 文件：`agent_server_new/app/bootstrap.py`
- 增加 env 开关：
  - `AGENT_SYMBOL_MEMORY_ENABLED`
- 开启时注入 `InMemorySymbolMemoryAdapter` 到 provider/recorder；关闭则传 `None`。

6. 测试
- 新增：
  - `agent_server_new/text/test_symbol_memory_context_injection.py`
  - `agent_server_new/text/test_symbol_memory_recording_workflow.py`
- 断言：
  - 注入字段存在且不破坏原有 `ExecutionPlan` 结构。
  - 同 symbol 多事件会累积形成可读取的 recent memory。

## 6. 风险与控制

主要风险：

1. 记忆噪声过高导致判断漂移。
2. 上下文过长导致成本/延迟上升。

控制手段：

1. 强制 Top-K 与字段白名单。
2. `summary` 与 `raw` 分层读取，不全量注入。
3. 通过 feature flag 灰度启用，保留快速回滚能力。

## 7. 里程碑与交付物

M1（Phase 0 完成）：

1. ports + in-memory adapter + ContextBuilder 注入 + Workflow 写回
2. 单测通过，开关默认关闭

M2（Phase 1 完成）：

1. Redis 持久化
2. 规则化摘要任务
3. 基础观测指标

M3（Phase 2 完成）：

1. DB 归档 + replay 差分
2. Markdown 复盘导出任务
