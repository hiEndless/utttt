# Verification Script Inventory

更新时间：2026-03-13

## 1. 当前状态

- `scripts/` 目录中的验证兼容壳已全部下线。
- 验证入口统一收敛到 `tools/local/*`、`tools/ci/*` 与 `verification/guards/*`。

## 2. 主入口

- 全量守卫：`tools/ci/new_arch_guards_full.sh`
  - 显式包含来源语义门禁：`check_source_semantics_guard.sh`
  - 显式包含 alternative source 单源契约门禁：`check_alternative_source_single_source_guard.sh`
- 快速验证：`tools/ci/verify_quick.sh`
  - 帮助：`bash tools/ci/verify_quick.sh --help`
- 回归验证：`tools/ci/verify_regression.sh`
  - 帮助：`bash tools/ci/verify_regression.sh --help`
- 夜间验证：`tools/ci/verify_nightly.sh`
  - 帮助：`bash tools/ci/verify_nightly.sh --help`
- 本地 quick 代理入口：`tools/local/verify_quick.sh`（代理到 `tools/ci/verify_quick.sh`）
- 本地 full 代理入口：`tools/local/verify_full.sh`（代理到 `tools/ci/new_arch_guards_full.sh`）
- 文档契约守卫聚合：`tools/local/check_docs_contracts_bundle.sh`
  - 失败排障提示：当 contract bundle 守卫失败时，执行标准排障命令。
  - 标准排障命令：`bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions`
- 发布基线对齐守卫：`tools/local/check_release_baseline_alignment.sh`
  - 失败提示：统一建议先执行 `bash tools/local/check_release_ready.sh`
- 发布文档排障块一致性守卫：`tools/local/check_release_triage_block_guard.sh`
  - 支持：`bash tools/local/check_release_triage_block_guard.sh --show-blocks`
- 发布文档最小复现片段一致性守卫：`tools/local/check_release_docs_repro_alignment_guard.sh`
  - 支持：`bash tools/local/check_release_docs_repro_alignment_guard.sh --show-missing`
- prod provider 门禁守卫：`tools/local/check_prod_provider_modes_guard.sh`
- 来源语义守卫：`tools/local/check_source_semantics_guard.sh`
- pipeline 语义字段锚点守卫：`tools/local/check_pipeline_semantic_terms_doc_guard.sh`
- alternative source 单源契约守卫：`tools/local/check_alternative_source_single_source_guard.sh`
- 一键发布就绪检查：`tools/local/check_release_ready.sh`
  - 内含：`verify_quick`、`new_arch_guards_full --quick`、`check_release_triage_block_guard.sh`、`check_release_baseline_alignment.sh --check-origin`
  - 支持：`bash tools/local/check_release_ready.sh --help`
  - 支持：`bash tools/local/check_release_ready.sh --print-summary-only`（仅输出门禁阈值摘要）
  - 支持：`bash tools/local/check_release_ready.sh --print-summary-only --summary-format json`（JSON 摘要）
  - 输出会先打印当前 readyz/confidence 门禁阈值摘要（用于发布记录）
  - JSON 摘要 schema：`verification/reports/release_gate_summary_v1.schema.json`
- quick 耗时剖析：`tools/local/profile_verify_quick_guards.sh`
- 脚本白名单检查：`tools/local/check_script_compat_whitelist.sh`
- feature 合同入口守卫：`tools/local/check_feature_contract_entry_guard.sh`
- feature 文档 source names 守卫：`tools/local/check_feature_docs_source_names_guard.sh`
- state 合同入口守卫：`tools/local/check_market_state_contract_entry_guard.sh`
- event_center 合同入口守卫：`tools/local/check_event_center_contract_entry_guard.sh`
- event_center runtime mode 门禁守卫：`tools/local/check_event_center_runtime_mode_guard.sh`
- CLI 帮助快照守卫：`tools/local/check_cli_help_snapshot_guard.sh`

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
- `check_source_semantics_guard.sh`
- `check_pipeline_semantic_terms_doc_guard.sh`
- `check_alternative_source_single_source_guard.sh`
- `check_cross_service_time_semantics_doc_guard.sh`
- `check_new_arch_guards_help_snapshot_guard.sh`
- `check_cli_help_snapshot_guard.sh`
- `check_contract_docs_canonical_layout_guard.sh`
- `verify_all.sh --quick`
- `pytest verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code`（锁定非法 provider_state 告警码链路）
- 可选观测：`WITH_AGENT_READYZ=1` 时追加 `aggregate_and_check.sh --with-agent-readyz --max-agent-readyz-level ${MAX_AGENT_READYZ_LEVEL:-red}`（默认不阻断 quick 主链路）

CI 约束：
- `VERIFY_QUICK_SKIP_SEMANTIC_CRITICAL=1` 与 `VERIFY_QUICK_SKIP_RELEASE_BASELINE_ALIGNMENT=1`
  仅用于本地调试链路；
- 在 CI 环境（`CI=true` 或 `GITHUB_ACTIONS=true`）若设置上述变量，`tools/ci/verify_quick.sh` 将直接失败（退出码 `2`）。

### 3.2 verify_regression

- `check_structure.sh`
- `check_script_compat_whitelist.sh`
- `check_new_arch_guards_help_snapshot_guard.sh`
- `check_cli_help_snapshot_guard.sh`
- `pytest verification/text/test_verify_ci_help.py`（锁定 regression/nightly --help 关键字段）
- `check_contract_docs_canonical_layout_guard.sh`
- `check_pipeline_semantic_terms_doc_guard.sh`
- `verify_all.sh --event-center-quick`
- `pytest verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code`（锁定非法 provider_state 告警码链路）
- `sync_contract_indexes.sh`
- `audit_semantics.sh`
- `check_semantic_warning_budget.sh`
- `aggregate_and_check.sh --with-agent-readyz --max-agent-readyz-level ${MAX_AGENT_READYZ_LEVEL:-red} --require-agent-readyz-report`

### 3.3 verify_nightly

- `check_structure.sh`
- `check_script_compat_whitelist.sh`
- `check_new_arch_guards_help_snapshot_guard.sh`
- `check_cli_help_snapshot_guard.sh`
- `check_contract_docs_canonical_layout_guard.sh`
- `check_pipeline_semantic_terms_doc_guard.sh`
- `verify_all.sh --report-json=verification/reports/nightly.latest.json`
- `pytest verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code`（锁定非法 provider_state 告警码链路）
- `sync_contract_indexes.sh`
- `audit_semantics.sh`
- `check_semantic_warning_budget.sh`
- `aggregate_and_check.sh --with-agent-readyz --max-legacy-confidence-ratio ${MAX_LEGACY_CONFIDENCE_RATIO:-0.05} --max-agent-readyz-level ${MAX_AGENT_READYZ_LEVEL:-yellow} --require-agent-readyz-report`

## 4. 历史映射

历史 `scripts/*` 到新入口的映射保留在：
- `verification/migration_map.yaml`

该映射仅用于审计与追溯，不再作为运行入口。
