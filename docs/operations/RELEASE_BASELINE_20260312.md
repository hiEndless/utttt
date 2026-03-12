# Release Baseline 2026-03-12

更新时间：2026-03-12

## 1. Baseline Tag

- tag: `refactor-guard-baseline-20260312`
- 当前指向: 以命令结果为准（`git rev-parse --short refactor-guard-baseline-20260312`）

## 2. 关键修复提交

- `9c2052c`：`execution-schema-mapping` 基线从 `v15` 升级到 `v16`，同步 code/schema/manifest/docs/tests。
- `699241a`：`verify_quick` 在 docs bundle 失败时自动输出 `--show-detected-versions` 调试信息。
- `0f83ab0`：operations 文档中统一标准排障命令文案。

## 3. 基线验证（本地）

- `bash tools/ci/verify_quick.sh` -> pass
- `bash tools/ci/new_arch_guards_full.sh --quick` -> pass

## 4. 标准排障命令

```bash
bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions
```

## 5. 备注

- 当前工作区仍存在若干未跟踪文件（与本次 baseline 无关），未纳入提交。
