# Operations Docs

Canonical operations docs:

- `README.md`（仓库导航入口）

- `ALERT_CODES.md`
- `DECISION_CONFIDENCE_MIGRATION.md`
- `VERIFICATION_SCRIPT_INVENTORY.md`
- `RELEASE_GATE_CHECKLIST_TEMPLATE.md`
- `VERIFICATION_COMPAT_WINDOW.md`
- `FEATURE_SERVICE_COMPAT_WRAPPER_DECOMMISSION.md`
- `MARKET_STATE_ENGINE_COMPAT_WRAPPER_DECOMMISSION.md`
- `VERIFICATION_API_DRAFT.md`
- `SEMANTIC_AUDIT_RUNBOOK.md`
- `DEV_PRIORITY_POLICY.md`
- `SCRIPT_COMPAT_WHITELIST.md`
- `CLI_HELP_SNAPSHOT.md`
- `NEW_ARCH_GUARDS_HELP_SNAPSHOT_RUNBOOK.md`
- `VERIFY_QUICK_DEDUP_MATRIX.md`
- `VERIFY_QUICK_TIMING_BASELINE.md`
- `PLACEHOLDER_INVENTORY_20260312.md`

使用建议：
- 本地 quick 入口优先使用 `tools/local/verify_quick.sh`（代理到 `tools/ci/verify_quick.sh`）。
- 本地 full 入口优先使用 `tools/local/verify_full.sh`（代理到 `tools/ci/new_arch_guards_full.sh`）。
- `verify_quick` 的 `--skip-semantic-critical-warning-guard` / `--skip-release-baseline-alignment` 仅限本地调试；
  CI 环境禁止启用对应 skip 变量（启用会直接失败）。
- readyz 门禁默认策略：
  - quick：默认关闭（`WITH_AGENT_READYZ=0`，可按需开启观测）
  - regression：默认启用，`MAX_AGENT_READYZ_LEVEL=red`，`REQUIRE_AGENT_READYZ_REPORT=1`
  - nightly：默认启用，`MAX_AGENT_READYZ_LEVEL=yellow`，`REQUIRE_AGENT_READYZ_REPORT=1`
- 详细矩阵与排障步骤见：`docs/operations/SEMANTIC_AUDIT_RUNBOOK.md`
