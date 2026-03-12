# Release Latest

更新时间：2026-03-13

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
