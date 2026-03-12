# Root Module Residual Cleanup Policy

更新时间：2026-03-12

## 范围

- `agent_server_new/`
- `execution_service/`
- `event_center_new/`
- `feature_service/`

以上目录在运行实现迁移到 `services/*` 后，仍保留了 docs/text/兼容层资产。

## 当前结论

1. `docs/`：保留（契约与迁移文档的有效来源）。
2. `text/`：暂时保留（大量被 `tools/local/*` 守卫脚本和 `verify_quick` 直接引用）。
3. 根目录 `__init__.py`：保留（兼容桥接，防止旧导入路径中断）。
4. `__pycache__/`：可删除（本次已清理）。

## 为什么不能立即删除 text/

当前守卫链路仍直接调用：
- `verification/auditors/agent_server_new/*.py`
- `verification/validators/execution_service/*.py`
- `verification/replay/event_center_new/*.py`（已迁移）
- `verification/validators/feature_service/*.py`

若直接删除，会导致：
- `tools/local/check_*` 脚本失败
- `tools/ci/verify_quick.sh` 失败
- 契约漂移守卫失效

## 可删除前置条件

仅在以下条件全部满足后，才删除对应根目录 `text/`：

1. 该目录测试已迁移到统一验证层（建议：`verification/*`）。
2. 所有 `tools/local/check_*` 与 `tools/ci/*` 路径已切换到新位置。
3. `pytest.ini` 收敛到新测试目录。
4. 连续 7 天主干 CI 全绿（无回滚）。

## 推荐迁移目标

1. 契约/schema类测试：迁入 `verification/validators`。
2. 语义一致性与不变量测试：迁入 `verification/auditors`。
3. 回放/对比测试：迁入 `verification/replay` 与 `verification/diff`。
4. 服务级单元测试：迁入 `services/<svc>/tests`（如后续建立该目录）。

## 清理状态（已完成）

1. `event_center_new/text` -> `verification/replay/event_center_new`
2. `feature_service/text` -> `verification/validators/feature_service`
3. `agent_server_new/text` -> `verification/auditors/agent_server_new`
4. `execution_service/text` -> `verification/validators/execution_service`
5. `market_state_engine/text` -> `verification/validators/market_state_engine`

## 当前状态

- 根目录服务模块仅保留：
  - `docs/` 文档与 schema 资产
  - 必要兼容层（如 `__init__.py`）
  - 少量服务特有静态配置（如 `market_state_engine/config`）
