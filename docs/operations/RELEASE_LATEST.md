# Release Latest

更新时间：2026-03-12

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
```

发布基线一致性检查（含远端）：

```bash
bash tools/local/check_release_baseline_alignment.sh --check-origin
```

一键发布就绪检查：

```bash
bash tools/local/check_release_ready.sh
```
