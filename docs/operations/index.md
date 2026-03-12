# Operations Docs

Canonical operations docs:

- `README.md`（仓库导航入口）

- `ALERT_CODES.md`
- `DECISION_CONFIDENCE_MIGRATION.md`
- `VERIFICATION_SCRIPT_INVENTORY.md`
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
