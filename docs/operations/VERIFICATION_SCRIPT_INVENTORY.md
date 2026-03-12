# Verification Script Inventory

更新时间：2026-03-12

## 1. 当前状态

- `scripts/` 目录中的验证兼容壳已全部下线。
- 验证入口统一收敛到 `tools/local/*`、`tools/ci/*` 与 `verification/guards/*`。

## 2. 主入口

- 全量守卫：`tools/ci/new_arch_guards_full.sh`
- 快速验证：`tools/ci/verify_quick.sh`
- 回归验证：`tools/ci/verify_regression.sh`
- 夜间验证：`tools/ci/verify_nightly.sh`
- 文档契约守卫聚合：`tools/local/check_docs_contracts_bundle.sh`
  - 失败排障提示：当 contract bundle 守卫失败时，执行标准排障命令。
  - 标准排障命令：`bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions`
- 发布基线对齐守卫：`tools/local/check_release_baseline_alignment.sh`
  - 失败提示：统一建议先执行 `bash tools/local/check_release_ready.sh`
- 发布文档排障块一致性守卫：`tools/local/check_release_triage_block_guard.sh`
- prod provider 门禁守卫：`tools/local/check_prod_provider_modes_guard.sh`
- 一键发布就绪检查：`tools/local/check_release_ready.sh`
  - 内含：`verify_quick`、`new_arch_guards_full --quick`、`check_release_triage_block_guard.sh`、`check_release_baseline_alignment.sh --check-origin`
- quick 耗时剖析：`tools/local/profile_verify_quick_guards.sh`
- 脚本白名单检查：`tools/local/check_script_compat_whitelist.sh`
- feature 合同入口守卫：`tools/local/check_feature_contract_entry_guard.sh`
- state 合同入口守卫：`tools/local/check_market_state_contract_entry_guard.sh`
- event_center 合同入口守卫：`tools/local/check_event_center_contract_entry_guard.sh`
- event_center runtime mode 门禁守卫：`tools/local/check_event_center_runtime_mode_guard.sh`

### 2.1 调试参数（contract bundle）

- 脚本：`tools/local/check_contract_change_bundle_guard.sh`
- 参数：`--show-detected-versions`
- 用途：输出 `BASE_REF` 与 `HEAD` 的版本探测值（`CONTRACT_INDEX` / `manifest` / `services/event_center_new/version.py` / `services/event_center_new/docs/runtime.md`），用于排查 runtime 版本锚点触发原因。

## 3. CI 入口关键阶段（显式）

### 3.1 verify_quick

- `check_structure.sh`
- `check_script_compat_whitelist.sh`
- `check_docs_contracts_bundle.sh`（包含 `test_contract_change_bundle_guard.py` 回归用例）
- `check_release_triage_block_guard.sh`
- `check_release_baseline_alignment.sh`
- `check_prod_provider_modes_guard.sh`
- `check_semantic_policy_guard.sh`
- `check_cross_service_time_semantics_doc_guard.sh`
- `check_new_arch_guards_help_snapshot_guard.sh`
- `check_contract_docs_canonical_layout_guard.sh`
- `verify_all.sh --quick`

### 3.2 verify_regression

- `check_structure.sh`
- `check_script_compat_whitelist.sh`
- `check_new_arch_guards_help_snapshot_guard.sh`
- `check_contract_docs_canonical_layout_guard.sh`
- `verify_all.sh --event-center-quick`
- `sync_contract_indexes.sh`
- `audit_semantics.sh`
- `check_semantic_warning_budget.sh`

### 3.3 verify_nightly

- `check_structure.sh`
- `check_script_compat_whitelist.sh`
- `check_new_arch_guards_help_snapshot_guard.sh`
- `check_contract_docs_canonical_layout_guard.sh`
- `verify_all.sh --report-json=verification/reports/nightly.latest.json`
- `sync_contract_indexes.sh`
- `audit_semantics.sh`
- `check_semantic_warning_budget.sh`
- `aggregate_and_check.sh`

## 4. 历史映射

历史 `scripts/*` 到新入口的映射保留在：
- `verification/migration_map.yaml`

该映射仅用于审计与追溯，不再作为运行入口。
