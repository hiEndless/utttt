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
- 脚本白名单检查：`tools/local/check_script_compat_whitelist.sh`

## 3. CI 入口关键阶段（显式）

### 3.1 verify_quick

- `check_structure.sh`
- `check_script_compat_whitelist.sh`
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
