# Verify Quick De-dup Matrix

更新时间：2026-03-12

## 1. 目标

明确 `tools/ci/verify_quick.sh` 与 `tools/ci/verify_all.sh --quick` 的职责边界，避免同一守卫在同一链路重复执行，降低耗时并提升日志可读性。

## 2. 当前链路

- 外层：`tools/ci/verify_quick.sh`
- 内层：`tools/ci/verify_all.sh --quick`（实际执行 `verification/run_suite.sh --suite=quick`）

## 3. 去重矩阵（当前）

| 守卫/步骤 | verify_quick 外层 | verify_all --quick 内层 | 备注 |
|---|---|---|---|
| `check_structure.sh` | Y | N | 外层基础结构守卫 |
| `check_script_compat_whitelist.sh` | Y | N | 外层基础守卫 |
| `check_docs_contracts_bundle.sh` | Y | N | 外层文档契约聚合守卫（含 `test_contract_change_bundle_guard.py`） |
| `check_release_baseline_alignment.sh` | Y | N | 外层发布基线一致性守卫（RELEASE_LATEST/tag/HEAD） |
| `check_prod_provider_modes_guard.sh` | Y | N | 外层 prod provider/sink 门禁守卫（agent+execution） |
| `check_contract_docs_index_guard.sh` | N | Y | 通过 `quick` suite 的 `contract_docs_index` 执行 |
| `check_contract_docs_index_help_snapshot_guard.sh` | N | Y | 同上 |
| `check_state_to_agent_contract_guard.sh` | N | Y | 通过 `state_to_agent` 执行 |
| `check_agent_to_execution_guard.sh` | N | Y | 通过 `agent_to_execution` 执行 |
| `sync_contract_indexes.sh` | Y | N | 外层后处理 |
| `audit_semantics.sh` | Y | N | 外层后处理 |
| `check_semantic_critical_warning_guard.sh` | Y | N | 外层语义红线守卫 |

结论：
- 当前 `verify_quick` 与 `verify_all --quick` 无显式重复守卫调用（按脚本入口维度）。
- 文档契约类守卫由外层 bundle 统一管理；contract index 与链路契约由内层 quick suite 负责。
- `contract bundle regression tests` 在外层执行，属于 docs bundle 子步骤，不在 quick suite 内重复执行。
- `verify_quick` 外层在 docs bundle 失败时会直接打印排障提示：
  标准排障命令：`bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions`。

## 4. 调整原则

1. 外层负责：基础结构、文档契约聚合、语义审计后处理。
2. 内层负责：跨服务链路契约（contract_docs_index/state_to_agent/agent_to_execution）。
3. 新增守卫时先落矩阵，再决定放外层或内层，避免双挂。

## 5. 维护动作

当以下文件变更时应同步更新本矩阵：
- `tools/ci/verify_quick.sh`
- `tools/ci/verify_all.sh`
- `verification/run_suite.sh`（尤其 `suite=quick` 分支）
- `tools/local/check_docs_contracts_bundle.sh`

固定排障约定：
- `verify_quick` 在 `check_docs_contracts_bundle.sh` 失败时，会自动执行
  标准排障命令：`bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions`
  并将探测值写入 CI 日志，便于 artifact 直接定位。
