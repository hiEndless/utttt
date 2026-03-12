# Market State Engine Compat Wrapper Decommission

更新时间：2026-03-12  
状态：in_progress (batch-c phase-1 completed)

## 1. 目标

在不影响联调稳定性的前提下，分批下线 `market_state_engine/*` 兼容壳，最终仅保留 `services/market_state_engine/src/*` 作为实现源。

## 2. 范围

当前兼容壳覆盖：

- `market_state_engine/{__init__,main,app,routes,contracts,service,errors,engine,msl}.py`
- `market_state_engine/adapters/**/*.py`
- `market_state_engine/ports/**/*.py`
- `market_state_engine/factors/**/*.py`
- `market_state_engine/state_inference/**/*.py`

## 3. 下线分批

### Batch 0（已完成，迁调用不删壳）

- 仓内业务与测试导入迁移到 `services.market_state_engine.src.*`（非 `market_state_engine/*` 目录）
- 新增守卫：`tools/local/check_market_state_legacy_imports.sh`

执行结果：

- 已完成（2026-03-12）

### Batch A（低风险，优先）

- 删除 `market_state_engine/{app,routes,contracts,errors,msl}.py` 兼容壳
- 保留 `service.py` / `engine.py`（模块桥接）与 `main.py`

前置门禁：

1. `bash tools/local/check_market_state_legacy_imports.sh --strict` 通过。
2. `./venv/bin/pytest -q market_state_engine/text` 通过。
3. `bash tools/ci/verify_quick.sh` 通过。

执行结果：

- 阶段1已完成（2026-03-12）：已删除 `app/routes/contracts/errors/msl`。
- 阶段2待执行：继续评估 `service.py` / `engine.py` / `main.py` 下线窗口。

### Batch B（中风险）

- 删除 `market_state_engine/adapters/**/*.py` 与 `market_state_engine/ports/**/*.py` 兼容壳
- 保留 `__init__.py`、`main.py`、`service.py`、`engine.py`

执行结果：

- 阶段1已完成（2026-03-12）：`adapters/**/*.py` 与 `ports/**/*.py` 兼容壳已删除。

### Batch C（高风险，最后）

- 删除 `market_state_engine/factors/**/*.py` 与 `market_state_engine/state_inference/**/*.py` 兼容壳
- 删除 `market_state_engine/{__init__.py,adapters/__init__.py,ports/__init__.py}`

执行结果：

- 阶段1已完成（2026-03-12）：`factors/**/*.py` 与 `state_inference/**/*.py` 兼容壳已删除。
- 阶段2待执行：评估 `__init__.py` 与 `main/service/engine` 的最终下线窗口。

### Batch D（收口）

- 删除 `market_state_engine/{service.py,engine.py,main.py}`
- `market_state_engine/` 仅保留必要文档/测试资产

## 4. 执行检查单（每批）

1. 删除目标兼容壳文件。
2. 扫描遗留导入：
   - `bash tools/local/check_market_state_legacy_imports.sh --strict`
3. 回归：
   - `./venv/bin/pytest -q market_state_engine/text`
   - `bash tools/ci/verify_quick.sh`
4. 更新文档：
   - `services/services_map.yaml`
   - `docs/architecture/SERVICES_PHASE2_MILESTONE.md`
   - `services/market_state_engine/README.md`

## 5. 回滚策略

若任一批次出现回归：

1. `git revert <commit>` 回滚该批删除提交。
2. 记录失败日志与残留导入位置。
3. 该批次退回“兼容壳保留”状态，下一迭代再执行。
