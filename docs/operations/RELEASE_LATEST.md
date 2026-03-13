# Release Latest

更新时间：2026-03-13

统一门禁模板：`docs/operations/RELEASE_GATE_CHECKLIST_TEMPLATE.md`

当前生效基线（single source）：

- branch: `master`
- commit: 以命令结果为准（`git rev-parse --short HEAD`）
- tag: `refactor-guard-baseline-20260312`
- tag commit: 以命令结果为准（`git rev-parse --short refactor-guard-baseline-20260312^{}`）

最小验收命令：

```bash
bash tools/ci/verify_quick.sh
bash tools/ci/new_arch_guards_full.sh --quick
```

标准排障命令：

```bash
bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions
rg -n "^\[CI_GUARD\]" quick_strict.log quick_lenient.log full_guard.log
cat guard_summary.quick_strict.log guard_summary.quick_lenient.log guard_summary.full.log
```

发布基线一致性检查（含远端）：

```bash
bash tools/local/check_release_baseline_alignment.sh --check-origin
```

一键发布就绪检查：

```bash
bash tools/local/check_release_ready.sh
bash tools/local/finalize_release_baseline.sh
```

发布检查补充（confidence 迁移门禁）：

1. 记录当次 CI 生效阈值：`MAX_LEGACY_CONFIDENCE_RATIO`（nightly 默认 `0.05`，可被环境变量覆盖）。
2. 记录聚合报告实际值：`execution_legacy_confidence_usage_ratio`（来自 `verification/reports/summary.latest.json`）。
3. 仅当 `execution_legacy_confidence_usage_ratio <= MAX_LEGACY_CONFIDENCE_RATIO` 时允许进入发布基线固化流程。

发布检查补充（agent readyz 门禁）：

1. 记录当次 CI 生效阈值：
   - regression：`MAX_AGENT_READYZ_LEVEL`（默认 `red`）、`REQUIRE_AGENT_READYZ_REPORT`（默认 `1`）
   - regression：`MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS`（默认 `-1`，忽略）
   - nightly：`MAX_AGENT_READYZ_LEVEL`（默认 `yellow`）、`REQUIRE_AGENT_READYZ_REPORT`（默认 `1`）
   - nightly：`MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS`（默认 `0`）
2. 记录聚合报告实际值（来自 `verification/reports/summary.latest.json`）：
   - `agent_readyz_status_level`
   - `agent_readyz_report_count`
   - `agent_readyz_error_count`
   - `agent_readyz_errors`
   - `decision_trace_schema_guard_invalid_records`
3. 放行条件：
   - `agent_readyz_report_count > 0`（当 `REQUIRE_AGENT_READYZ_REPORT=1`）
   - `agent_readyz_status_level <= MAX_AGENT_READYZ_LEVEL`
   - `decision_trace_schema_guard_invalid_records <= MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS`（当阈值 >= 0）

发布排障最小复现（release gate schema）：

```bash
git checkout -b tmp/release-gate-schema-repro
echo "// repro" >> verification/reports/release_gate_summary_v1.schema.json
bash tools/local/check_contract_change_bundle_guard.sh
```

预期：守卫提示 schema 变更触发四件套，需同步更新索引/契约文档/运行说明/守卫测试。
