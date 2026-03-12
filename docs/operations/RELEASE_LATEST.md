# Release Latest

更新时间：2026-03-12

当前生效基线（single source）：

- branch: `master`
- commit: `e2d2252`
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
