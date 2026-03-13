# Codex 执行包：RUN 001（T00 + T01）

本 run 目标：先把 `agent_server_new` 的“目录结构/导入/端口定义”做实，确保后续重构可以在可运行、可测试的地基上持续推进。

对应任务：
- T00：最小可运行基线（仅做 smoke：import + app/workflow 可实例化）
- T01：修复 `agent_server_new` 的 ports 路径一致性（补齐 `ports.data.*`）

---

## A. 范围（Scope）

只允许修改或新增以下路径（白名单）：
- `agent_server_new/ports/`（允许新增 `ports/data/` 子包）
- `agent_server_new/app/context_builder.py`
- `agent_server_new/app/workflows/trade_event_workflow.py`
- `agent_server_new/adapters/active_events_stub.py`
- `agent_server_new/adapters/position_context_stub.py`
- （可选）`agent_server_new/tests/`（新增最小 import 测试）

禁止修改：
- `agent_server/`（旧系统）
- `feature_service/`、`market_state_engine/`、`event_center_new/`
- `agent_server_new/domain/` 下的业务逻辑（本 run 只修结构与端口，不改决策语义）

---

## B. 契约（Contract）

必须保持不变：
- 决策输出契约：`agent_server_new/domain/contracts.py` 中 `ExecutionPlan/SignalVerdict` 的字段含义不变
- `EventContext` 的字段含义不变（可以为了导入修复做最小改动，但不能改字段语义与命名）

允许新增：
- 新增 ports 协议文件（Protocol）与必要的 `__init__.py` 导出
- 新增最小测试用例（只做 import/smoke，不做复杂业务断言）

---

## C. 任务拆解（Steps）

### Step 1：补齐 `agent_server_new.ports.data` 包

当前代码存在导入但目录缺失：
- `agent_server_new.ports.data.active_events_provider`
- `agent_server_new.ports.data.position_context_provider`

要求：
- 新建目录 `agent_server_new/ports/data/`
- 新建文件：
  - `agent_server_new/ports/data/__init__.py`
  - `agent_server_new/ports/data/active_events_provider.py`
  - `agent_server_new/ports/data/position_context_provider.py`

定义规范：
- 只定义“抽象协议（Protocol）”，不引入具体实现细节
- 返回值类型保持当前调用方预期：
  - `get_active_events(exchange, symbol)` → `List[Dict[str, Any]]`
  - `get_position_context(exchange, symbol)` → `Dict[str, Any]`
- 协议命名必须与现有导入保持一致：`ActiveEventsProvider`、`PositionContextProvider`

### Step 2：校验并统一所有引用点

确保以下文件导入均可解析（不再报 ModuleNotFoundError）：
- `agent_server_new/app/context_builder.py`
- `agent_server_new/app/workflows/trade_event_workflow.py`
- `agent_server_new/adapters/active_events_stub.py`
- `agent_server_new/adapters/position_context_stub.py`

要求：
- 只做“导入路径一致性修复”，不改变行为
- 若发现额外的 `ports.data.*` 相关引用，必须一并修复

### Step 3：（可选但推荐）增加最小 smoke 测试

目的：防止后续 run 再次引入导入错误。

建议新增：
- `agent_server_new/tests/test_imports.py`

断言内容建议只包含：
- `import agent_server_new.app.context_builder`
- `import agent_server_new.app.workflows.trade_event_workflow`
- `import agent_server_new.adapters.active_events_stub`
- `import agent_server_new.adapters.position_context_stub`

---

## D. 验收（Acceptance）

必须全部通过：

1) 代码可导入（最小 smoke）

建议执行：
```bash
python -c "import agent_server_new.app.context_builder; import agent_server_new.app.workflows.trade_event_workflow; print('agent_server_new imports ok')"
```

2) 目录引用一致性检查

建议执行：
```bash
python -c "from agent_server_new.ports.data.active_events_provider import ActiveEventsProvider; from agent_server_new.ports.data.position_context_provider import PositionContextProvider; print('ports.data ok')"
```

3) （若新增 tests）单测通过

按仓库现有测试方式执行；若没有统一 runner，至少确保 `python -m py_compile` 能编译通过：
```bash
python -m py_compile agent_server_new/app/context_builder.py agent_server_new/app/workflows/trade_event_workflow.py
```

---

## E. 回滚（Rollback）

若本 run 导致导入链更混乱或出现循环依赖：
- 优先回滚到“仅新增 `ports/data/*`，不改其他文件”的状态
- 保留所有新增 ports 协议文件（它们是稳定地基），只回滚对 workflow/context_builder 的非必要改动

---

## F. 完成输出（codex 需输出的结果）

codex 完成本 run 后，需要在回复中给出：
- 修改/新增文件列表
- 验收执行结果（每条验收命令的输出摘要）
- 若新增 tests：说明如何运行
