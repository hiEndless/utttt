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
- `agent_server_new/text/*.py`
- `execution_service/text/*.py`
- `verification/replay/event_center_new/*.py`（已迁移）
- `feature_service/text/*.py`

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

## 清理顺序（建议）

1. `event_center_new/text`（与 replay/selected schema 相关，边界清晰，优先迁）。
2. `feature_service/text`（规模小，迁移成本低）。
3. `agent_server_new/text`（与 workflow 绑定较多，中等风险）。
4. `execution_service/text`（数量最多、守卫最密集，最后迁）。

## 本次已完成

- 清理 `agent_server_new|execution_service|event_center_new|feature_service` 下全部 `__pycache__/` 目录。
