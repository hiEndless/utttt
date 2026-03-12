# Feature Service Compat Wrapper Decommission

更新时间：2026-03-12  
状态：completed (batch-c completed)

## 1. 目标

在不影响运行稳定性的前提下，分批下线 `feature_service/*` 兼容壳，最终仅保留 `services/feature_service/src/*` 作为实现源。

## 2. 范围

当前已进入兼容壳状态的路径：

- `feature_service/main.py`
- `feature_service/app.py`
- `feature_service/routes.py`
- `feature_service/service.py`
- `feature_service/contracts.py`
- `feature_service/providers/*.py`
- `feature_service/normalizers/*.py`
- `feature_service/ports/*.py`
- `feature_service/providers/market_structure_migrated/**/*.py`（`behavioral/behavior_output.py` 为特例）

## 3. 下线分批

### Batch A（低风险，优先）

- `feature_service/{app,routes,service,contracts}.py`
- `feature_service/{ports,normalizers}/**/*.py`

前置门禁：

1. `bash tools/local/check_feature_legacy_imports.sh --strict` 通过。
2. `./venv/bin/pytest -q verification/validators/feature_service` 通过。
3. `bash tools/ci/verify_quick.sh` 通过。

执行结果：

- 已完成（2026-03-12）

### Batch B（中风险）

- `feature_service/providers/*.py`（不含 `market_structure_migrated/`）

前置门禁：

1. Batch A 已稳定一个迭代周期。
2. `feature_service` 生产/回放链路无兼容壳相关告警。
3. `./venv/bin/pytest -q verification/validators/feature_service` 与 quick CI 持续通过。

执行结果：

- 已完成（2026-03-12）

### Batch D（收口）

- `feature_service/main.py`

执行结果：

- 已完成（2026-03-12）

### Batch C（高风险，最后）

- `feature_service/providers/market_structure_migrated/**/*.py`

前置门禁：

1. 测试不再 monkeypatch 旧路径模块符号。
2. `services/feature_service/src/providers/market_structure_migrated/` 全量回归稳定。
3. quick + regression + nightly 全部通过。

执行结果：

- 已完成（2026-03-12）

## 4. 执行检查单（每批）

1. 删除目标兼容壳文件。
2. 全仓扫描遗留 import：
   - `bash tools/local/check_feature_legacy_imports.sh --strict`
3. 回归：
   - `./venv/bin/pytest -q verification/validators/feature_service`
   - `bash tools/ci/verify_quick.sh`
4. 更新文档：
   - `services/services_map.yaml`
   - `docs/architecture/SERVICES_PHASE2_MILESTONE.md`
   - `feature_service/README.md`

## 5. 回滚策略

若任一批次出现回归：

1. 直接 `git revert <commit>` 回滚该批删除提交。
2. 保留失败日志与失败用例，定位残留 import 或 monkeypatch 依赖。
3. 将该批次降级回“兼容壳保留”状态，进入下一迭代再评估。

## 6. 当前建议起步

已完成，进入维护阶段：

1. `bash tools/local/check_feature_legacy_imports.sh --strict`
2. `./venv/bin/pytest -q verification/validators/feature_service`
3. `bash tools/ci/verify_quick.sh`
